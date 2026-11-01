# -*- coding: utf-8 -*-
"""Kiểm tra cấu hình bảo mật của dự án An Tâm Home (bản 2310).

Chạy:  python scripts/security_audit.py
Không sửa gì — chỉ đọc và in kết quả ✗/⚠/✓ để người vận hành xử lý.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OK = "[OK]  "
WARN = "[CANH BAO]"
FAIL = "[THIEU]"


def section(title: str) -> None:
    print()
    print("=" * 62)
    print(title)
    print("=" * 62)


def check_server() -> None:
    section("1. Server (Flask)")
    for name in ("server/security_middleware.py", "server/app_security.py", "server/app_state.py"):
        print(f"{OK if (ROOT / name).exists() else FAIL} {name}")
    app = (ROOT / "server/app.py").read_text(encoding="utf-8")
    for marker, label in (
        ("install_rate_limiting", "rate limiting theo nhóm"),
        ("install_request_guard", "request guard (JSON + mẫu tấn công)"),
        ("install_extra_headers", "HSTS / COOP / Permissions-Policy"),
        ("/api/health", "health check công khai"),
    ):
        print(f"{OK if marker in app else FAIL} {label}")
    from smarthome.config import load_config

    cfg = load_config(ROOT / "config.yaml")
    server_cfg = cfg.get("server", {})
    print(f"{WARN} server: {server_cfg.get('host')}:{server_cfg.get('port')} — dùng HTTPS khi ra ngoài LAN (SMART_HOME_SSL_CERT/KEY)")
    webhook = (cfg.get("alerts", {}) or {}).get("webhook_url") or ""
    print(f"{OK if webhook else WARN} webhook cảnh báo CRITICAL {'da cau hinh' if webhook else 'chua cau hinh (alerts.webhook_url)'}")


def check_env_secrets() -> None:
    section("2. Khoa bi mat")
    env_file = ROOT / ".env"
    if env_file.exists():
        print(f"{OK} .env ton tai (khong doc noi dung — khong in khoa ra log)")
    else:
        print(f"{WARN} .env chua co — sao chep tu .env.example")
    print(f"{OK if (ROOT / '.env.example').exists() else FAIL} .env.example mau cau hinh")
    key_file = ROOT / "data/secret_key"
    print(f"{OK if key_file.exists() else WARN} data/secret_key {'da co' if key_file.exists() else 'chua co (se tu sinh khi chay server)'}")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines() if (ROOT / ".gitignore").exists() else []
    ignored = any(line.strip() in {".env", "/.env"} or line.strip().startswith(".env") for line in gitignore)
    print(f"{OK if ignored else WARN} .env phai nam trong .gitignore")


def check_android() -> None:
    section("3. Android collector")
    main_pkg = ROOT / "android_collector/app/src/main"
    manifest = (main_pkg / "AndroidManifest.xml").read_text(encoding="utf-8")
    nsc = main_pkg / "res/xml/network_security_config.xml"
    pins = main_pkg / "res/raw/cert_pins.txt"
    kt_files = list((main_pkg / "java").rglob("*.kt"))
    kt_all = "\n".join(p.read_text(encoding="utf-8") for p in kt_files)

    print(f"{OK if nsc.exists() else FAIL} network_security_config.xml")
    if nsc.exists():
        content = nsc.read_text(encoding="utf-8")
        print(f"{OK if 'pin-set' in content else WARN} pin-set trong NSC (domain HTTPS)")
        print(f"{OK if 'REPLACE_WITH' not in content else WARN} da thay pin placeholder trong NSC")
    print(f"{OK if pins.exists() else FAIL} res/raw/cert_pins.txt")
    if pins.exists():
        pin_lines = [l.strip() for l in pins.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.strip().startswith("#")]
        print(f"{OK if pin_lines else WARN} {len(pin_lines)} pin thuc da dien trong cert_pins.txt")
    print(f"{OK if 'networkSecurityConfig' in manifest else FAIL} manifest tham chieu networkSecurityConfig")
    print(f"{OK if 'CertificatePinner' in kt_all else FAIL} CertificatePinner trong Kotlin")
    print(f"{OK if 'lowercase()' in kt_all else FAIL} hashBssid viet thuong truoc khi bam")
    cleartext_attr = 'android:usesCleartextTraffic' in manifest
    print(f"{OK if not cleartext_attr else WARN} manifest de NSC quyet dinh cleartext (khong xung dot)")


def check_tests() -> None:
    section("4. Kiem tra nhanh kha chay")
    try:
        result = subprocess.run(
            [str(ROOT / ".venv/Scripts/python.exe"), "-c", "import smarthome.ap_hashing as m; print(m.hash_bssid('aa:bb:cc:dd:ee:ff'))"],
            cwd=ROOT, capture_output=True, text=True, timeout=60, encoding="utf-8",
        )
        if result.returncode == 0:
            print(f"{OK} ap_hashing khớp vector: {result.stdout.strip()}")
        else:
            print(f"{FAIL} khong nap duoc smarthome.ap_hashing: {result.stderr.strip()[:200]}")
    except Exception as exc:  # môi trường thiếu .venv v.v.
        print(f"{WARN} khong chay duoc python kiem tra: {exc}")


def check_secret_scan() -> None:
    section("5. Quet secret hard-code")
    patterns = [
        (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "khoa rieng"),
        (re.compile(r"(?i)(api[_-]?key|secret|password)\s*=\s*[\"'][^\"']{16,}[\"']"), "secret hard-code"),
    ]
    skip_dirs = {".git", "__pycache__", ".venv", "node_modules", ".tmp", ".gradle", ".pytest_cache", ".playwright-cli", "build"}
    found = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            if not file.endswith((".py", ".kt", ".xml", ".yaml", ".yml", ".json", ".js", ".html")):
                continue
            path = Path(base) / file
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern, label in patterns:
                if pattern.search(content):
                    print(f"{WARN} {label} nghi van tai {path.relative_to(ROOT)}")
                    found += 1
    if not found:
        print(f"{OK} khong thay secret/khoa rieng nao trong source")


def main() -> None:
    print("KIEM TRA BAO MAT — An Tâm Home")
    check_server()
    check_env_secrets()
    check_android()
    check_tests()
    check_secret_scan()
    print()
    print("Hoan tat. Muc [CANH BAO]/[THIEU] can xu ly theo SECURITY.md.")


if __name__ == "__main__":
    main()
