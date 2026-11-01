# -*- coding: utf-8 -*-
"""Middleware bảo mật dùng chung cho server.

Bổ sung cho các lớp đã có trong ``app_security`` (CSP, nosniff,
X-Frame-Options, AttemptLimiter):

- ``RateLimiter``: giới hạn tần suất theo nhóm endpoint ``/api/*`` bằng
  sliding window. Hỗ trợ Redis cho distributed deployment (nhiều instance
  Flask chung quota), fallback về RAM nếu Redis không cấu hình.
- ``install_request_guard``: chỉ nhận body JSON cho thao tác ghi (lớp phòng
  thủ CSRF thứ hai, bên cạnh cookie SameSite=Lax) và chặn sớm query/path
  chứa mẫu SQL injection/XSS. Truy vấn thật vẫn là tham số hóa + Jinja
  escape; lớp này chỉ giảm nhiễu log.
- ``install_extra_headers``: HSTS (chỉ khi HTTPS), Permissions-Policy,
  Cross-Origin-* và ``Cache-Control: no-store`` cho API.
- ``install_json_errors``: lỗi 4xx/5xx của API trả JSON thay vì trang HTML,
  để app Android và PWA đọc được ``error``.

Lưu ý vận hành: chỉ đặt ``SMART_HOME_TRUST_PROXY=1`` khi server thật sự
nằm sau reverse proxy tin cậy. Nếu bật mà không có proxy, client tự gửi
``X-Forwarded-For`` sẽ vượt được rate limit.
"""
from __future__ import annotations

from collections import deque
import os
import re
import threading
import time
from typing import Optional

from flask import Response, g, jsonify, request, session as flask_session
from werkzeug.exceptions import HTTPException, InternalServerError

from app_security import session_expired

# ----------------------------------------------------------------------------
# Redis support (optional)
# ----------------------------------------------------------------------------
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

def get_redis_client():
    """Tạo Redis client từ env vars. Trả về None nếu không cấu hình."""
    if not REDIS_AVAILABLE:
        return None
    host = os.getenv("REDIS_HOST", "").strip()
    if not host:
        return None
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD", "").strip() or None
    try:
        client = redis.Redis(
            host=host, port=port, db=db, password=password,
            socket_connect_timeout=2, socket_timeout=2,
            decode_responses=True
        )
        # Test connection
        client.ping()
        return client
    except Exception:
        return None

_redis_client = get_redis_client()

# ----------------------------------------------------------------------------
# Rate limiting
# ----------------------------------------------------------------------------

# Ngưỡng theo nhóm endpoint: (số request, cửa sổ giây). Đây là máy chủ gia
# đình trong LAN, nên ngưỡng đủ rộng cho dashboard (3 request/2 giây ≈ 90
# request/phút), demo và cảm biến, nhưng vẫn chặn được dò mật khẩu hàng loạt.
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "auth": (30, 60),
    # Một phiên hiệu chuẩn hợp lệ gửi ~200 mẫu trong vài phút (3 phiên ×
    # nhiều hướng); 240/phút đủ rộng cho script thu thập thật.
    "collect": (240, 60),
    "scan": (240, 60),
    "sensor": (240, 60),
    "api": (300, 60),
}

BLOCK_SECONDS = 60
MAX_TRACKED_CLIENTS = 4096
TRUST_PROXY_ENV = "SMART_HOME_TRUST_PROXY"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HEALTH_PATH = "/api/health"


def _trust_proxy() -> bool:
    """Chỉ tin X-Forwarded-For khi người vận hành bật rõ ràng."""
    return os.getenv(TRUST_PROXY_ENV, "0").strip() == "1"


class RateLimiter:
    """Giới hạn tần suất sliding window theo (nhóm endpoint, IP client).

    Hỗ trợ 2 chế độ:
    - Redis (distributed): dùng sorted set với TTL, đồng bộ giữa nhiều instance
    - RAM (fallback): deque trong bộ nhớ, chỉ hoạt động single-instance
    """

    def __init__(self) -> None:
        self._redis = _redis_client
        self._use_redis = self._redis is not None
        if not self._use_redis:
            self._requests: dict[str, deque[float]] = {}
            self._blocked: dict[str, float] = {}
            self._lock = threading.Lock()

    def _client_id(self) -> str:
        """Xác định client ID: IP + UA hash. Trust proxy nếu cấu hình."""
        if _trust_proxy():
            forwarded = request.headers.get("X-Forwarded-For", "")
            ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr
        else:
            ip = request.remote_addr or "?"
        ua = request.headers.get("User-Agent", "").encode("utf-8", "ignore")
        return f"{ip}:{hashlib.sha256(ua).hexdigest()[:8]}"

    def _rate_limit_key(self, group: str, client_id: str) -> str:
        return f"ratelimit:{group}:{client_id}"

    def _block_key(self, client_id: str) -> str:
        return f"ratelimit:block:{client_id}"

    def check(self, group: str, limit: int, window_seconds: int) -> tuple[bool, dict]:
        """Kiểm tra rate limit. Trả về (allowed, info_dict)."""
        client_id = self._client_id()
        key = self._rate_limit_key(group, client_id)
        block_key = self._block_key(client_id)
        now = time.time()

        if self._use_redis:
            return self._check_redis(group, limit, window_seconds, key, block_key, now)
        else:
            return self._check_ram(group, limit, window_seconds, key, block_key, now)

    def _check_redis(self, group: str, limit: int, window_seconds: int,
                     key: str, block_key: str, now: float) -> tuple[bool, dict]:
        """Rate limit dùng Redis sorted set (sliding window log)."""
        try:
            pipe = self._redis.pipeline()
            window_start = now - window_seconds

            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Count current requests
            pipe.zcard(key)
            # Check block
            pipe.get(block_key)
            results = pipe.execute()

            current_count = results[1]
            blocked_until = results[2]

            if blocked_until and float(blocked_until) > now:
                return False, {"retry_after": int(float(blocked_until) - now) + 1}

            if current_count >= limit:
                # Block for BLOCK_SECONDS
                self._redis.setex(block_key, BLOCK_SECONDS, str(now + BLOCK_SECONDS))
                return False, {"retry_after": BLOCK_SECONDS}

            # Add current request
            self._redis.zadd(key, {str(now): now})
            self._redis.expire(key, window_seconds + 1)
            return True, {"remaining": limit - current_count - 1}

        except Exception:
            # Fallback to RAM on Redis error
            self._use_redis = False
            self._requests = {}
            self._blocked = {}
            self._lock = threading.Lock()
            return self._check_ram(group, limit, window_seconds, key, block_key, now)

    def _check_ram(self, group: str, limit: int, window_seconds: int,
                   key: str, block_key: str, now: float) -> tuple[bool, dict]:
        """Rate limit dùng RAM (fallback)."""
        with self._lock:
            # Clean up old entries if too many clients
            if len(self._requests) > MAX_TRACKED_CLIENTS:
                oldest = min(self._requests.items(), key=lambda x: x[1][0] if x[1] else now)
                self._requests.pop(oldest[0], None)
                self._blocked.pop(oldest[0], None)

            # Check block
            unblock_at = self._blocked.get(key)
            if unblock_at and now < unblock_at:
                return False, {"retry_after": int(unblock_at - now) + 1}
            elif unblock_at:
                del self._blocked[key]

            # Sliding window
            window = self._requests.setdefault(key, deque())
            window_start = now - window_seconds
            while window and window[0] < window_start:
                window.popleft()

            if len(window) >= limit:
                self._blocked[key] = now + BLOCK_SECONDS
                return False, {"retry_after": BLOCK_SECONDS}

            window.append(now)
            return True, {"remaining": limit - len(window)}

    @staticmethod
    def _client_id() -> str:
        if _trust_proxy():
            forwarded = request.headers.get("X-Forwarded-For", "")
            if forwarded:
                candidate = forwarded.split(",")[0].strip()
                if candidate:
                    return candidate
        return request.remote_addr or "unknown"

    def _prune(self, now: float) -> None:
        """Dọn cửa sổ hết hạn và giữ số khóa dưới mức trần."""
        expired_blocks = [key for key, until in self._blocked.items() if until <= now]
        for key in expired_blocks:
            self._blocked.pop(key, None)

        # Cửa sổ bị chặn cũng phải có trần: kẻ tấn công đổi IP liên tục có
        # thể tạo nhiều khóa chặn hơn số client đang theo dõi.
        blocked_overflow = len(self._blocked) - MAX_TRACKED_CLIENTS
        if blocked_overflow > 0:
            soonest = sorted(self._blocked.items(), key=lambda item: item[1])
            for key, _until in soonest[:blocked_overflow]:
                self._blocked.pop(key, None)

        stale_windows = [
            key for key, window in self._requests.items()
            if not window or window[-1] <= now - 3600
        ]
        for key in stale_windows:
            self._requests.pop(key, None)

        overflow = len(self._requests) - MAX_TRACKED_CLIENTS
        if overflow > 0:
            oldest = sorted(
                self._requests.items(),
                key=lambda item: item[1][-1] if item[1] else 0.0,
            )
            for key, _window in oldest[:overflow]:
                self._requests.pop(key, None)

    def check(self, group: str, limit: int, window_seconds: int) -> tuple[bool, dict]:
        """Trả về (được phép, thông tin hạn mức) cho request hiện tại."""
        key = f"{group}:{self._client_id()}"
        now = time.monotonic()

        with self._lock:
            self._prune(now)

            unblock_at = self._blocked.get(key)
            if unblock_at is not None:
                if now < unblock_at:
                    return False, {"retry_after": int(unblock_at - now) + 1}
                del self._blocked[key]

            window = self._requests.setdefault(key, deque())
            while window and window[0] <= now - window_seconds:
                window.popleft()
            if len(window) >= limit:
                # Xóa cửa sổ khi chặn: hết thời gian chặn client bắt đầu lại
                # từ 0 thay vì tiếp tục dính ngưỡng ngay lập tức.
                self._requests.pop(key, None)
                self._blocked[key] = now + BLOCK_SECONDS
                return False, {"retry_after": BLOCK_SECONDS}

            window.append(now)
            return True, {"remaining": limit - len(window)}

    def reset(self) -> None:
        """Xóa toàn bộ bộ đếm — dùng giữa các test."""
        with self._lock:
            self._requests.clear()
            self._blocked.clear()


def rate_limit_group(path: str) -> str:
    """Chọn nhóm hạn mức theo đường dẫn (gọi trước khi vào endpoint)."""
    if path.startswith("/api/auth/") or path == "/api/homes/join":
        return "auth"
    if path == "/api/collect":
        return "collect"
    if path == "/api/scan":
        return "scan"
    if path.startswith("/api/sensor"):
        return "sensor"
    return "api"


def install_rate_limiting(app) -> None:
    """Gắn before_request giới hạn tần suất cho API; bỏ qua health check."""
    limiter = RateLimiter()
    app.extensions["rate_limiter"] = limiter

    @app.before_request
    def enforce_rate_limit():
        if not request.path.startswith("/api/") or request.path == HEALTH_PATH:
            return None
        group = rate_limit_group(request.path)
        limit, window = RATE_LIMITS[group]
        allowed, info = limiter.check(group, limit, window)
        g.rate_limit_remaining = info.get("remaining")
        if not allowed:
            retry_after = int(info.get("retry_after", BLOCK_SECONDS))
            response = jsonify({
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "Quá nhiều yêu cầu, vui lòng thử lại sau",
                "retry_after": retry_after,
            })
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        return None


def reset_rate_limits(app) -> None:
    """Xóa bộ đếm rate limit của app (fixture test gọi giữa các test)."""
    limiter = app.extensions.get("rate_limiter")
    if limiter is not None:
        limiter.reset()


# ----------------------------------------------------------------------------
# Session expiry
# ----------------------------------------------------------------------------

def install_session_guard(app) -> None:
    """Vô hiệu hóa phiên quá hạn ngay khi request tới.

    Cookie Flask chỉ được ký, không có hạn phía server: cookie bị chụp lại
    (HTTP trong LAN, malware) hợp lệ vô thời hạn và logout không thu hồi
    được bản sao đã chụp. Mỗi phiên mang dấu ``_iat`` (xem
    ``app_security.mark_session_issued``); quá
    ``SMART_HOME_SESSION_MAX_AGE_HOURS`` (mặc định 7 ngày) là bị xóa, client
    phải đăng nhập lại.
    """

    @app.before_request
    def enforce_session_expiry():
        if flask_session.get("user_id") and session_expired():
            flask_session.clear()
        return None


# ----------------------------------------------------------------------------
# Request guard: JSON-only cho thao tác ghi + lọc mẫu tấn công
# ----------------------------------------------------------------------------

# Mẫu tấn công phổ biến theo OWASP. Bản ghi chốt vẫn là truy vấn tham số hóa
# và Jinja escape; lớp này chỉ để chặn sớm request tầm thường.
SQLI_PATTERNS = [
    re.compile(r"\b(UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO|DELETE\s+FROM)\b", re.I),
    re.compile(r"\b(OR|AND)\b\s+\d+\s*=\s*\d+", re.I),
    re.compile(r";\s*--"),
]
XSS_PATTERNS = [
    re.compile(r"<\s*script", re.I),
    re.compile(r"javascript\s*:", re.I),
    re.compile(r"\bon(error|load|click)\s*=", re.I),
    re.compile(r"<\s*iframe", re.I),
]


def _looks_malicious(value: str) -> Optional[str]:
    """Trả về loại tấn công phát hiện được, hoặc None nếu an toàn."""
    for pattern in SQLI_PATTERNS:
        if pattern.search(value):
            return "SQLi"
    for pattern in XSS_PATTERNS:
        if pattern.search(value):
            return "XSS"
    return None


def _request_has_body() -> bool:
    """True nếu request có body. Body rỗng vẫn được phép cho POST không tham số.

    Werkzeug test client và nhiều client thật không gửi ``Content-Length``
    khi body rỗng, nên chỉ coi là có body khi có độ dài > 0 hoặc chunked.
    """
    if request.content_length is not None:
        return request.content_length > 0
    return "chunked" in request.headers.get("Transfer-Encoding", "").lower()


def install_request_guard(app) -> None:
    """Chặn body không phải JSON và query/path chứa mẫu tấn công.

    HTML form chỉ gửi được ``application/x-www-form-urlencoded``,
    ``multipart/form-data`` hoặc ``text/plain`` — không gửi được
    ``application/json``. Vì vậy yêu cầu JSON cho mọi thao tác ghi có body
    là lớp phòng thủ CSRF thứ hai, không phụ thuộc SameSite của trình duyệt.
    Các POST không body (logout, reset, training/start) vẫn hợp lệ.
    """

    @app.before_request
    def guard_request():
        if not request.path.startswith("/api/"):
            return None

        if request.method in WRITE_METHODS and _request_has_body() and not request.is_json:
            return jsonify({
                "error": "UNSUPPORTED_MEDIA_TYPE",
                "message": "Thao tác ghi phải gửi body JSON (Content-Type: application/json)",
            }), 415

        checked: list[tuple[str, str]] = [
            (f"query.{key}", str(value)) for key, value in request.args.items()
        ]
        # ``view_args`` là None khi URL không khớp route nào (404); bản cũ
        # gọi .items() trực tiếp nên biến 404 thành 500.
        checked.extend(
            (f"path.{key}", str(value))
            for key, value in (request.view_args or {}).items()
        )
        for context, value in checked:
            kind = _looks_malicious(value)
            if kind:
                app.logger.warning(
                    "[Bao mat] Chan request %s (%s) tai %s", kind, context, request.path
                )
                return jsonify({
                    "error": "INVALID_INPUT",
                    "message": "Yêu cầu chứa dữ liệu không hợp lệ",
                }), 400
        return None


# ----------------------------------------------------------------------------
# Headers bổ sung
# ----------------------------------------------------------------------------

def install_extra_headers(app) -> None:
    """Bổ sung HSTS, Permissions-Policy, Cross-Origin-* và no-store cho API.

    CSP/nosniff/X-Frame-Options đã có trong ``app_security`` nên ở đây dùng
    ``setdefault`` để không ghi đè cấu hình một nơi khác.

    ``accelerometer`` và ``gyroscope`` phải là ``(self)``: dashboard dùng
    DeviceMotion để phát hiện va chạm/vị trí điện thoại. Đặt ``()`` sẽ chặn
    tính năng trên iPhone (Safari tôn trọng Permissions-Policy).
    """

    @app.after_request
    def extra_security_headers(response: Response) -> Response:
        # HSTS chỉ có nghĩa khi kết nối thật sự là HTTPS. Gửi trên HTTP
        # khiến trình duyệt ghi nhớ một domain chưa từng chạy TLS.
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        response.headers.setdefault(
            "Permissions-Policy",
            "accelerometer=(self), gyroscope=(self), magnetometer=(self), "
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


# ----------------------------------------------------------------------------
# JSON error handlers
# ----------------------------------------------------------------------------

_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "RATE_LIMIT_EXCEEDED",
}


def _api_request() -> bool:
    return request.path.startswith("/api/")


def _json_error(status: int, code: str, message: str):
    response = jsonify({"error": code, "message": message})
    response.status_code = status
    return response


def install_json_errors(app) -> None:
    """Lỗi của API trả JSON; trang HTML vẫn dùng trang lỗi mặc định."""

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if not _api_request():
            return error.get_response()
        code = _ERROR_CODES.get(error.code or 500, "HTTP_ERROR")
        return _json_error(
            error.code or 500,
            code,
            error.description or "Yêu cầu không hợp lệ",
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        # HTTPException đã có handler riêng; ở đây là lỗi lập trình/thời gian
        # chạy. Không trả traceback hay đường dẫn file ra ngoài.
        app.logger.exception("[Loi] Request %s %s that bai", request.method, request.path)
        if _api_request():
            return _json_error(
                500,
                "INTERNAL_ERROR",
                "Máy chủ gặp lỗi, vui lòng thử lại",
            )
        return InternalServerError()
