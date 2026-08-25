@echo off
title EdgeSecurity AI - Launcher

echo ==================================
echo     Iniciando EdgeSecurity AI
echo ==================================

cd /d "%~dp0"

if not exist ".venv" (
    echo [1/5] Criando ambiente virtual Python...
    py -m venv .venv
)

echo [2/5] Ativando ambiente virtual...
call .venv\Scripts\activate

echo [3/5] Instalando/Atualizando dependencias...
python -m pip install --upgrade pip
pip install -r backend\requirements.txt

echo [4/5] Iniciando Backend (FastAPI + YOLO edgev1.pt)...
start "EdgeSecurity Backend" cmd /k "cd backend && ..\.venv\Scripts\python.exe run.py"

timeout /t 5 /nobreak >nul

echo [5/5] Iniciando Servidor Frontend...
start "EdgeSecurity Frontend" cmd /k ".\.venv\Scripts\python.exe serve.py"

timeout /t 3 /nobreak >nul

echo Abrindo interface no navegador...
start http://127.0.0.1:5500

echo.
echo EdgeSecurity executando com sucesso!
echo Mantenha as janelas de comando abertas durante o uso.
pause