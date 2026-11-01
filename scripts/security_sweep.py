"""Quét phân quyền toàn bộ endpoint /api/*.

Rủi ro chính của việc tách app.py thành blueprint là một endpoint bị mất
trang trí @login_required. Script này liệt kê mọi route /api/* trong URL map
rồi gọi KHÔNG kèm phiên đăng nhập, để tìm endpoint trả dữ liệu hoặc thực hiện
thao tác mà không cần xác thực.

Chạy:  .venv\\Scripts\\python.exe scripts\\security_sweep.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))

import app as appmod  # noqa: E402  (server/app.py)

# Endpoint công khai có chủ đích — không tính là hở.
PUBLIC = {
    "/api/auth/register",   # tạo tài khoản (đã có register_limiter 10 lần/giờ theo IP)
    "/api/auth/login",      # đăng nhập (đã có login_limiter 5 lần/15 phút theo email)
    "/api/health",          # health check, không trả dữ liệu người dùng
    # Đăng xuất khi chưa đăng nhập trả 200 là ĐÚNG: nó chỉ xoá phiên rỗng, không
    # tiết lộ gì và cũng không thao tác trên dữ liệu của ai. Idempotent by design.
    "/api/auth/logout",
}

# Thân request tối thiểu cho từng loại route để không bị 400 vì thiếu dữ liệu
# (400 cũng là "đã chặn", nhưng ta muốn phân biệt rõ với 200).
BODY = json.dumps({"name": "x", "email": "x@example.com", "password": "x" * 10,
                   "code": "000000", "wifi": {}, "room": "x", "session_id": "s"})

METHOD_BODY = {"POST": BODY, "PUT": BODY, "PATCH": BODY}


def main() -> int:
    appmod.app.config["TESTING"] = True
    rules = sorted(
        (rule.rule, sorted(rule.methods - {"HEAD", "OPTIONS"}))
        for rule in appmod.app.url_map.iter_rules()
        if rule.rule.startswith("/api/")
    )

    leaks: list[tuple[str, str, int, str]] = []
    checked = 0
    # Token thiết bị sai: phải bị từ chối, không được âm thầm hạ xuống session.
    bad_bearer = {"Authorization": "Bearer ath_khong-he-ton-tai"}

    with appmod.app.test_client() as client:
        for rule, methods in rules:
            path = rule.replace("<int:home_id>", "1").replace("<int:room_id>", "1") \
                       .replace("<int:device_id>", "1").replace("<int:user_id>", "1")
            for method in methods:
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                checked += 1
                response = client.open(
                    path, method=method,
                    data=METHOD_BODY.get(method, ""),
                    content_type="application/json",
                )
                public = rule in PUBLIC
                # 401 = hàng rào xác thực đã chặn. 403/404/400/415/409 cũng là đã chặn.
                if response.status_code == 200 and not public:
                    leaks.append((method, rule, response.status_code, "trả 200 khi chưa đăng nhập"))

                # Thêm: bearer sai không được biến thành quyền của session.
                response_bearer = client.open(
                    path, method=method,
                    data=METHOD_BODY.get(method, ""),
                    content_type="application/json",
                    headers=bad_bearer,
                )
                if response_bearer.status_code == 200 and not public:
                    leaks.append((method, rule, response_bearer.status_code, "token sai vẫn trả 200"))

    print(f"Đã quét {checked} tổ hợp (route, method) trong {len(rules)} route /api/*")
    print()
    if leaks:
        print("PHÁT HIỆN HỞ PHÂN QUYỀN:")
        for method, rule, status, note in leaks:
            print(f"  [X] {method:6} {rule:45} HTTP {status} — {note}")
        return 1
    print("Không endpoint nào trả dữ liệu khi chưa xác thực (ngoài danh sách công khai).")
    print("Danh sách công khai có chủ đích:", ", ".join(sorted(PUBLIC)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
