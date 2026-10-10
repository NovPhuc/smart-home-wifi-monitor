# Phụ lục A: Hướng dẫn cài đặt môi trường

## Windows PowerShell

```powershell
cd smart-home-wifi-monitor
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="src"
python server/app.py
```

## Linux/macOS

```bash
cd smart-home-wifi-monitor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python server/app.py
```

## VS Code

Mở folder và chọn launch config "Run Flask Server" hoặc "Run Server + Browser".
