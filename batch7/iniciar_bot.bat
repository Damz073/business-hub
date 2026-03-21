@echo off
setlocal

cd /d %~dp0

echo ===============================
echo Iniciando ambiente virtual...
echo ===============================

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    if exist venv\Scripts\activate.bat (
        call venv\Scripts\activate.bat
    ) else (
        echo Ambiente virtual nao encontrado em .venv ou venv.
        pause
        exit /b 1
    )
)

echo ===============================
echo Iniciando servidor FastAPI
echo Lendo variaveis do arquivo .env, se existir
echo ===============================

python -m uvicorn app.main:app --port 8000

pause
