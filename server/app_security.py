"""Bảo mật: khóa ký session, bộ chặn dò, header trình duyệt, vệ sinh CSV."""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import os
import secrets
import threading
import time

from flask import Response
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]


def resolve_secret_key() -> str:
    """Khóa ký session cookie.

    Ưu tiên biến môi trường SMART_HOME_SECRET_KEY (README đã hướng dẫn).
    Nếu không có, sinh khóa ngẫu nhiên và lưu vào file data/secret_key để
    phiên đăng nhập (kể cả app Android khôi phục phiên) không mất sau mỗi
    lần khởi động lại. Bản cũ dùng chuỗi cố định
    "change-this-development-secret" — ai đọc được source có thể tự ký
    cookie để giả mạo đăng nhập, nên không bao giờ dùng khóa mặc định.
    """
    from_env = os.getenv("SMART_HOME_SECRET_KEY", "").strip()
    if from_env:
        return from_env
    database_path = Path(os.getenv("SMART_HOME_DATABASE", ROOT / "data" / "smarthome.db"))
    key_file = database_path.parent / "secret_key"
    try:
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        key = secrets.token_hex(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key, encoding="utf-8")
        print(f"[Bao mat] SMART_HOME_SECRET_KEY chua dat — da sinh khoa moi, luu tai {key_file} (khong dua len Git).")
        return key
    except OSError:
        print("[Bao mat] SMART_HOME_SECRET_KEY chua dat — dung khoa ngau nhien cho phien nay, doi sau khi restart.")
        return secrets.token_hex(32)


class AttemptLimiter:
    """Chặn dò mật khẩu / dò mã chia sẻ bằng cách thử lặp.

    Mỗi khóa (email khi đăng nhập, user khi tham gia nhà) chỉ được thất bại
    tối đa ``max_attempts`` lần trong ``window_seconds``; thành công thì xóa
    đếm. Bộ đếm nằm trong RAM — khởi động lại server là xóa — đủ cho máy chủ
    gia đình mà không cần thêm thư viện. Mốc 10.000 khóa chặn phình bộ nhớ
    khi bị dò hàng loạt email khác nhau.
    """

    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = int(max_attempts)
        self.window_seconds = float(window_seconds)
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_blocked(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            attempts = self._failures[key]
            while attempts and now - attempts[0] > self.window_seconds:
                attempts.popleft()
            return len(attempts) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            if len(self._failures) > 10_000:
                self._failures.clear()
            self._failures[key].append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset_all(self) -> None:
        with self._lock:
            self._failures.clear()


# Hash giả chỉ để tốn thời gian như một lần kiểm tra thật, chống đoán email
# nào đã đăng ký qua độ trễ phản hồi (timing attack).
DUMMY_PASSWORD_HASH = generate_password_hash("tai-khoan-khong-ton-tai")


def secure_cookie_requested() -> bool:
    """Cookie Secure bật khi env yêu cầu, hoặc tự bật khi server chạy HTTPS."""
    if os.getenv("SMART_HOME_SECURE_COOKIE") is not None:
        return os.getenv("SMART_HOME_SECURE_COOKIE") == "1"
    return bool(os.getenv("SMART_HOME_SSL_CERT") and os.getenv("SMART_HOME_SSL_KEY"))


def apply_security_headers(response: Response) -> Response:
    """Header bảo mật cơ bản cho trình duyệt.

    - nosniff: chặn trình duyệt đoán kiểu nội dung.
    - X-Frame-Options / frame-ancestors: chặn nhúng dashboard trong iframe
      (clickjacking).
    - CSP: chỉ cho phép tài nguyên cùng nguồn. style-src cần 'unsafe-inline'
      vì app.js vẽ thanh xác suất bằng thuộc tính style nội tuyến
      (style="transform:scaleX(...)").
    """
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    return response


def csv_formula_safe(value) -> str:
    """Chống "CSV injection" khi mở file export bằng Excel/LibreOffice.

    Ô văn bản bắt đầu bằng ``=`` ``+`` ``-`` ``@`` có thể bị hiểu là công
    thức (ví dụ tên phòng do người dùng tự đặt). Thêm dấu nháy đơn phía
    trước để Excel đọc nguyên chuỗi. Chỉ áp dụng cho các cột văn bản —
    cột RSSI là số âm thật và phải giữ nguyên.
    """
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text
