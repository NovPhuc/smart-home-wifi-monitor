"""Điểm vào WSGI cho production (gunicorn/uwsgi).

`Dockerfile` ở stage ``prod`` trước đây chạy ``python server/app.py`` — đó là
Werkzeug dev server, chỉ dùng để phát triển: một tiến trình, không có worker
pool, cảnh báo đỏ khi chạy thật, và không chịu được nhiều kết nối SSE cùng lúc.
Module này tách phần "đối tượng ứng dụng" ra khỏi phần "tự chạy server" để
gunicorn import được.

Chạy trong container:

    gunicorn --bind 0.0.0.0:5000 --worker-class gthread \\
             --workers 2 --threads 8 --timeout 300 server.wsgi:application

Chọn ``gthread`` chứ không phải ``sync`` vì dashboard dùng Server-Sent Events
(``/api/stream``): worker đồng bộ sẽ giữ một tiến trình cho mỗi kết nối SSE và
chặn các request khác. ``--timeout 300`` để SSE không bị gunicorn cắt giữa
chừng (heartbeat 15 giây nên thực tế không chạm ngưỡng này).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Gunicorn chạy với cwd=/app trong container, nhưng vẫn thêm tường minh để file
# này import được cả khi chạy từ nơi khác (ví dụ `gunicorn --chdir`).
for extra in (ROOT / "src", ROOT / "server"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

# `app.py` đã tạo Flask app ở cấp module (``app = create_app()``) và tự đăng ký
# route, middleware, blueprint. Không gọi create_app() lần nữa ở đây, nếu không
# sẽ có hai app và các singleton (db, engine, limiter) bị tách đôi.
from app import app as application  # noqa: E402

# Một số PaaS/gunicorn mặc định tìm biến tên ``app``.
app = application

__all__ = ["application", "app"]
