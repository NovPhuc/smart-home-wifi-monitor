# -*- coding: utf-8 -*-
"""Backup an toàn cho SQLite của An Tâm Home.

- Dùng sqlite backup API (src -> dest qua .backup()) thay vì copy file thô:
  an toàn khi DB đang ghi (WAL), không cần dừng server.
- Tùy chọn đồng bộ lên node phụ / cloud bằng rclone hoặc scp qua biến môi
  trường BACKUP_REMOTE — tương ứng hướng phát triển "lưu trữ phân tán"
  trong báo cáo (mục 10.3).

Ví dụ:
    python scripts/backup_db.py                          # backup cục bộ data/backups/
    python scripts/backup_db.py --keep 14                # giữ 14 bản gần nhất
    python scripts/backup_db.py --remote "rclone remote:antam-backup"
    python scripts/backup_db.py --remote "user@host:/srv/backup"
"""
from __future__ import annotations

import argparse
import io
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "smarthome.db"


def backup(db_path: Path, out_dir: Path, keep: int) -> Path:
    if not db_path.exists():
        raise SystemExit(f"Không tìm thấy database: {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = out_dir / f"smarthome_{stamp}.db"

    src = sqlite3.connect(str(db_path))
    try:
        # Kiểm tra trước khi backup: DB hỏng thì dừng, không lưu bản hỏng.
        ok = src.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise SystemExit(f"Database hỏng (integrity_check: {ok}) — KHÔNG backup.")
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)  # backup API: chốt trạng thái nhất quán, không khóa ghi lâu
        finally:
            dst.close()
    finally:
        src.close()

    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"Đã backup: {target} ({size_mb:.2f} MB)")

    # Kiểm tra bản backup đọc được
    check = sqlite3.connect(str(target))
    try:
        tables = check.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        print(f"Bản backup có {tables} bảng.")
    finally:
        check.close()

    # Xoá bản cũ, giữ `keep` bản mới nhất
    backups = sorted(out_dir.glob("smarthome_*.db"))
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink()
        print(f"Đã xoá bản cũ: {old.name}")
    return target


def sync_remote(target: Path, remote: str) -> None:
    """Đẩy bản backup lên node phụ. Hỗ trợ rclone (khuyến nghị) hoặc scp."""
    if remote.startswith("rclone"):
        cmd = ["rclone", "copy", str(target), remote]
    else:
        cmd = ["scp", str(target), remote]
    print("Đồng bộ:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("Đồng bộ thành công.")
    else:
        print(f"Đồng bộ THẤT BẠI (exit {result.returncode}): {result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description="Backup SQLite an toàn cho An Tâm Home")
    parser.add_argument("--database", default=str(DEFAULT_DB))
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "backups"))
    parser.add_argument("--keep", type=int, default=7, help="Số bản giữ lại (mặc định 7)")
    parser.add_argument("--remote", default=os.getenv("BACKUP_REMOTE", "").strip(),
                        help="rclone remote hoặc scp target; mặc định lấy từ BACKUP_REMOTE")
    args = parser.parse_args()

    target = backup(Path(args.database), Path(args.out_dir), args.keep)
    if args.remote:
        sync_remote(target, args.remote)
    else:
        print("Chưa cấu hình BACKUP_REMOTE — bản backup chỉ nằm cục bộ.")


if __name__ == "__main__":
    main()
