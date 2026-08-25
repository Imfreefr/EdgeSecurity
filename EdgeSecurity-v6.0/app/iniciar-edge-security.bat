@echo off
cd /d "%~dp0"
start "EdgeSecurity API" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul
start "EdgeSecurity Frontend" cmd /k "python serve.py"
start http://localhost:5500
