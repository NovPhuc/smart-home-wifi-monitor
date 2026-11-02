"""Thăm dò rate limiter: kiểm chứng hai tính chất quan trọng của bản phân tán.

Chạy:  .venv\\Scripts\\python.exe scripts\\rate_limit_probe.py

Cần Redis đang chạy và biến REDIS_HOST trỏ tới nó:

    docker run -d --name an-tam-redis-test -p 6399:6379 redis:7-alpine
    $env:REDIS_HOST='127.0.0.1'; $env:REDIS_PORT='6399'

Hai câu hỏi:

1. **Nguyên tử hay không?** Nếu `check()` đọc số đếm rồi mới ghi (check-then-act)
   thì nhiều request đồng thời cùng thấy "còn chỗ" và cùng ghi ⇒ số request được
   cho qua VƯỢT ngưỡng. Đây đúng là thứ mà bản phân tán phải chống.
2. **Có chia sẻ giữa các tiến trình không?** Hai tiến trình riêng biệt dùng chung
   Redis phải cộng dồn vào cùng một hạn mức; chế độ RAM thì mỗi tiến trình một
   hạn mức riêng.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))

os.environ.setdefault("SMART_HOME_TRUST_PROXY", "0")

from flask import Flask  # noqa: E402
import security_middleware as sm  # noqa: E402

app = Flask(__name__)


def probe_atomicity(limit: int = 10, threads: int = 60) -> dict:
    """Bắn `threads` request đồng thời với cùng một client, đếm số được cho qua."""
    limiter = sm.RateLimiter()
    mode = "redis" if limiter._use_redis else "ram"

    # Xoá trạng thái cũ của khoá này trước khi đo.
    if limiter._use_redis:
        for key in limiter._redis.scan_iter(match="ratelimit:*", count=1000):
            limiter._redis.delete(key)

    allowed = []
    lock = threading.Lock()
    barrier = threading.Barrier(threads)

    def one() -> None:
        with app.test_request_context("/api/auth/login", environ_base={"REMOTE_ADDR": "203.0.113.7"}):
            barrier.wait()                      # tất cả cùng lao vào một lúc
            ok, _info = limiter.check("probe", limit, 60)
        with lock:
            allowed.append(ok)

    workers = [threading.Thread(target=one) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    passed = sum(1 for value in allowed if value)
    return {"mode": mode, "limit": limit, "threads": threads, "allowed": passed}


def probe_shared_across_processes(limit: int = 5) -> dict:
    """Một tiến trình con dùng chung Redis: hạn mức phải được cộng dồn."""
    import json
    import subprocess

    limiter = sm.RateLimiter()
    mode = "redis" if limiter._use_redis else "ram"

    child_code = (
        "import os,sys,json;"
        f"sys.path.insert(0, r'{ROOT / 'src'}'); sys.path.insert(0, r'{ROOT / 'server'}');"
        "from flask import Flask; import security_middleware as sm;"
        "app=Flask(__name__); lim=sm.RateLimiter();"
        "ctx=app.test_request_context('/api/auth/login', environ_base={'REMOTE_ADDR':'203.0.113.9'});"
        "ctx.push();"
        "res=[lim.check('shared', %d, 60)[0] for _ in range(%d)];"
        "print(json.dumps(res))" % (limit, limit)
    )

    if limiter._use_redis:
        for key in limiter._redis.scan_iter(match="ratelimit:*", count=1000):
            limiter._redis.delete(key)

    child = subprocess.run([sys.executable, "-c", child_code], capture_output=True, text=True,
                           env={**os.environ}, cwd=str(ROOT))
    try:
        child_results = json.loads(child.stdout.strip().splitlines()[-1])
    except Exception:
        child_results = []
    child_allowed = sum(1 for value in child_results if value)

    parent_allowed = 0
    with app.test_request_context("/api/auth/login", environ_base={"REMOTE_ADDR": "203.0.113.9"}):
        for _ in range(limit):
            if limiter.check("shared", limit, 60)[0]:
                parent_allowed += 1

    return {
        "mode": mode, "limit": limit,
        "child_allowed": child_allowed, "parent_allowed": parent_allowed,
        "total_allowed": child_allowed + parent_allowed,
        "child_stderr": child.stderr.strip()[-200:] if child.returncode != 0 else "",
    }


def main() -> int:
    limiter = sm.RateLimiter()
    print("=" * 68)
    print("THĂM DÒ RATE LIMITER")
    print("=" * 68)
    print(f"  REDIS_HOST        : {os.getenv('REDIS_HOST', '(chưa đặt)')}:{os.getenv('REDIS_PORT', '6379')}")
    print(f"  redis package     : {'có' if sm.REDIS_AVAILABLE else 'KHÔNG'}")
    print(f"  chế độ đang dùng  : {'REDIS (phân tán)' if limiter._use_redis else 'RAM (một tiến trình)'}")
    print()

    atomic = probe_atomicity()
    print("1. Tính nguyên tử (60 request đồng thời, ngưỡng 10)")
    print(f"   chế độ {atomic['mode'].upper()} · cho qua {atomic['allowed']}/{atomic['threads']} · ngưỡng {atomic['limit']}")
    if atomic["mode"] == "redis":
        if atomic["allowed"] > atomic["limit"]:
            print(f"   => VƯỢT NGƯỠNG {atomic['allowed'] - atomic['limit']} request: check-then-act không nguyên tử")
        else:
            print("   => đúng ngưỡng: có nguyên tử")
    print()

    shared = probe_shared_across_processes()
    print("2. Chia sẻ giữa hai tiến trình (mỗi bên 5 request, ngưỡng 5)")
    print(f"   chế độ {shared['mode'].upper()}")
    print(f"   tiến trình con {shared['child_allowed']} + tiến trình cha {shared['parent_allowed']}"
          f" = {shared['total_allowed']} (ngưỡng {shared['limit']})")
    if shared["child_stderr"]:
        print(f"   stderr con: {shared['child_stderr']}")
    if shared["mode"] == "redis":
        if shared["total_allowed"] <= shared["limit"]:
            print("   => hạn mức được chia sẻ đúng giữa hai tiến trình")
        else:
            print(f"   => KHÔNG chia sẻ: tổng {shared['total_allowed']} > ngưỡng {shared['limit']}")
    print()

    client_id_note = "dùng UA" if "sha256" in sm.RateLimiter._client_id.__doc__ else "chỉ IP (xem chú thích hàm)"
    print(f"3. _client_id hiệu lực : {client_id_note}")
    print(f"   số định nghĩa trong class: {sm.RateLimiter.__dict__.get('_client_id').__class__.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
