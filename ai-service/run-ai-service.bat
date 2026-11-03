@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title AI Service - Oral Exam Practice [FastAPI Port 8000]

echo ========================================================
echo   KHOI DONG AI SERVICE - ORAL EXAM PRACTICE (PORT 8000)
echo ========================================================

REM 0. Giai phong tien trinh cu dang chiem cong 8000 (neu co)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [0/3] Phat hien tien trinh cu dang chiem cong 8000 [PID %%a], dang giai phong...
    taskkill /F /PID %%a /T >nul 2>&1
)

REM 1. Kiem tra va tao moi truong ao .venv neu chua co
if exist ".venv\Scripts\python.exe" goto VENV_FOUND

echo [1/3] Dang tao moi truong ao Python .venv ...
python -m venv .venv --system-site-packages
if errorlevel 1 (
    echo [LOI] Khong the tao .venv. Vui long kiem tra Python da duoc cai dat trong PATH.
    pause
    exit /b 1
)
echo [2/3] Dang cai dat cac thu vien can thiet vao .venv ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e .
goto CHECK_ENV

:VENV_FOUND
echo [1/3] Da tim thay moi truong ao: %~dp0.venv

:CHECK_ENV
REM 2. Kiem tra file cau hinh .env
if exist ".env" goto ENV_FOUND
if exist ".env.example" (
    echo [2/3] Chua co file .env, dang tao tu .env.example ...
    copy /Y ".env.example" ".env" >nul
    echo       Vui long cap nhat GEMINI_API_KEY va GROQ_API_KEY trong ai-service\.env!
    goto RUN_SERVER
)
:ENV_FOUND
echo [2/3] Da nap file cau hinh: %~dp0.env

:RUN_SERVER
REM 3. Kich hoat .venv va chay FastAPI voi Uvicorn
echo [3/3] Dang khoi chay FastAPI + Uvicorn ...
echo       - API Base URL : http://localhost:8000
echo       - Health Check : http://localhost:8000/ai/health
echo       - Swagger UI   : http://localhost:8000/docs
echo       (Nhan Ctrl+C de dung dich vu)
echo ========================================================
call ".venv\Scripts\activate.bat"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --access-log

echo.
echo [THONG BAO] Dich vu FastAPI da dung.
pause
endlocal
