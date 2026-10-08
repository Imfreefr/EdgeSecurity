@echo off
cd /d "%~dp0"
python tools\connect_ultralytics.py
if errorlevel 1 (
  echo Nao foi possivel abrir a janela. Confira a instalacao do Python.
  pause
)
