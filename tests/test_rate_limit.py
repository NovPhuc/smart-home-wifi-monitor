"""Test hồi quy cho RateLimiter (server/security_middleware.py).

Bối cảnh: class này từng bị dán hai lần thân class vào cùng một file, sinh ra
hai định nghĩa `check`. Bản thứ hai (bản Python dùng) đi thẳng vào
`with self._lock:` mà không xét `_use_redis`, trong khi `__init__` chỉ tạo
`_lock` khi KHÔNG dùng Redis. Hệ quả: hễ đặt `REDIS_HOST` — đúng cấu hình của
`docker-compose.prod.yml` — thì mọi request bị rate limit ném
`AttributeError: 'RateLimiter' object has no attribute '_lock'` và trả HTTP 500.
`/api/health` không bị giới hạn nên smoke test qua cửa đó không phát hiện được.

Các test dưới đây không cần Redis thật: chúng kiểm cấu trúc class và dùng một
Redis giả để chạy đúng nhánh phân tán.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))

from flask import Flask  # noqa: E402

import security_middleware as sm  # noqa: E402


class FakeRedis:
    """Redis giả đủ dùng cho nhánh rate limit: chỉ ĐẾM lời gọi script.

    Không mô phỏng ngữ nghĩa sorted set — việc kiểm chứng tính đúng của script
    Lua cần Redis thật, xem `scripts/rate_limit_probe.py`. Ở đây chỉ cần chứng
    minh đường phân tán được chọn và không ném lỗi.
    """

    def __init__(self) -> None:
        self.script_calls = 0
        self.deleted: list[str] = []

    def register_script(self, _source: str):
        def run(keys=None, args=None, client=None):
            self.script_calls += 1
            return [1, 10]                     # cho qua, còn 10 chỗ
        return run

    def scan_iter(self, match=None, count=None):
        return iter(["ratelimit:fake:1", "ratelimit:fake:2"])

    def delete(self, key):
        self.deleted.append(key)


@pytest.fixture()
def flask_app():
    app = Flask(__name__)
    return app


def test_class_chi_co_mot_dinh_nghia_check():
    """Hai định nghĩa `check` trong cùng class là nguồn gốc của lỗi HTTP 500."""
    assert sum(1 for name in sm.RateLimiter.__dict__ if name == "check") == 1


def test_class_chi_co_mot_dinh_nghia_client_id():
    assert sum(1 for name in sm.RateLimiter.__dict__ if name == "_client_id") == 1


def test_che_do_redis_van_tao_san_cau_truc_ram(monkeypatch):
    """Dù dùng Redis vẫn phải có `_lock`/`_requests`/`_blocked` cho đường dự phòng."""
    monkeypatch.setattr(sm, "_redis_client", FakeRedis())
    limiter = sm.RateLimiter()
    assert limiter._use_redis is True
    for attr in ("_lock", "_requests", "_blocked"):
        assert hasattr(limiter, attr), f"thiếu {attr} ở chế độ Redis"


def test_che_do_redis_goi_script_va_khong_bao_loi(monkeypatch, flask_app):
    fake = FakeRedis()
    monkeypatch.setattr(sm, "_redis_client", fake)
    limiter = sm.RateLimiter()
    with flask_app.test_request_context("/api/auth/login", environ_base={"REMOTE_ADDR": "198.51.100.4"}):
        allowed, info = limiter.check("auth", 30, 60)
    assert allowed is True
    assert fake.script_calls == 1
    assert info["remaining"] == 10


def test_redis_loi_thi_roi_ve_ram_chu_khong_no_ra(monkeypatch, flask_app):
    """Redis hỏng giữa chừng: phải chuyển sang RAM, không được ném lỗi ra ngoài."""

    class BrokenRedis(FakeRedis):
        def register_script(self, _source):
            def run(keys=None, args=None, client=None):
                raise ConnectionError("redis đã chết")
            return run

    monkeypatch.setattr(sm, "_redis_client", BrokenRedis())
    limiter = sm.RateLimiter()
    with flask_app.test_request_context("/api/auth/login", environ_base={"REMOTE_ADDR": "198.51.100.5"}):
        allowed, _info = limiter.check("auth", 3, 60)
    assert allowed is True
    assert limiter._use_redis is False            # đã hạ cấp
    assert hasattr(limiter, "_lock")              # và RAM dùng được


def test_client_id_chi_dung_ip_khong_dung_user_agent(flask_app):
    """UA do client tự đặt: đưa vào khoá là tự cho kẻ tấn công thêm bucket."""
    limiter = sm.RateLimiter()
    with flask_app.test_request_context(
        "/api/auth/login",
        environ_base={"REMOTE_ADDR": "203.0.113.20"},
        headers={"User-Agent": "KeTanCong/1.0"},
    ):
        first = limiter._client_id()
    with flask_app.test_request_context(
        "/api/auth/login",
        environ_base={"REMOTE_ADDR": "203.0.113.20"},
        headers={"User-Agent": "TrinhDuyetKhac/9.9"},
    ):
        second = limiter._client_id()
    assert first == second == "203.0.113.20"


def test_che_do_ram_van_nguyen_tu_khi_nhieu_luong(flask_app):
    """60 luồng cùng lúc với ngưỡng 10: chỉ đúng 10 được qua."""
    limiter = sm.RateLimiter()
    assert limiter._use_redis is False

    limit, threads = 10, 60
    results: list[bool] = []
    lock = threading.Lock()
    barrier = threading.Barrier(threads)

    def one() -> None:
        with flask_app.test_request_context("/api/auth/login", environ_base={"REMOTE_ADDR": "203.0.113.30"}):
            barrier.wait()
            allowed, _info = limiter.check("ram-atomic", limit, 60)
        with lock:
            results.append(allowed)

    workers = [threading.Thread(target=one) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert len(results) == threads
    assert sum(1 for value in results if value) == limit
