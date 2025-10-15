@echo off
REM Start Scalping Trainer API (single worker) with optional env vars

SETLOCAL ENABLEDELAYEDEXPANSION

REM Configure environment (edit as needed)
REM set ALLOWED_ORIGINS=https://your-frontend.example.com
REM set CORS_ALLOW_CREDENTIALS=true

REM Activate venv if present
IF EXIST "%~dp0..\venv\Scripts\activate.bat" (
  CALL "%~dp0..\venv\Scripts\activate.bat"
)

REM Change to repo root
PUSHD "%~dp0..\"

REM Start uvicorn
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --log-level info

POPD
ENDLOCAL
