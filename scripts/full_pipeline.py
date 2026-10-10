from __future__ import annotations
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*parts):
    cmd = [sys.executable, *map(str, parts)]
    print("\n$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    run(ROOT / "scripts/generate_synthetic_data.py")
    run(ROOT / "scripts/prepare_data.py")
    run(ROOT / "scripts/train_room.py")
    run(ROOT / "scripts/evaluate_room.py")
    run(ROOT / "scripts/train_baselines.py")
    run(ROOT / "scripts/train_anomaly.py")
    run(ROOT / "scripts/evaluate_anomaly.py")
    print("\nPipeline complete. Start dashboard with: python server/app.py")


if __name__ == "__main__":
    main()
