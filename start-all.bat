@echo off
chcp 65001 >nul
setlocal

if /I "%~1"=="--be" goto RUN_BACKEND
if /I "%~1"=="--fe" goto RUN_FRONTEND

echo ========================================================
echo   KHOI DONG TOAN BO HE THONG AI ORAL EXAM PRACTICE
echo ========================================================
echo   [1] AI Service (FastAPI)     : http://localhost:8000
echo       Swagger UI               : http://localhost:8000/docs
echo   [2] Backend (Spring Boot)    : http://localhost:8080
echo   [3] Frontend (Angular)       : http://localhost:4200
echo ========================================================
echo   Luu y: Dam bao PostgreSQL dang chay (localhost:5432)
echo          voi database "ai_oral_exam_practice".
echo ========================================================
echo.

start "AI Service - FastAPI (Port 8000)" cmd /k ""%~dp0ai-service\run-ai-service.bat""
start "Backend - Spring Boot (Port 8080)" cmd /k ""%~f0" --be"
start "Frontend - Angular (Port 4200)" cmd /k ""%~f0" --fe"

echo Da mo 3 cua so Terminal cho AI Service, Backend va Frontend.
echo Ban co the mo trinh duyet tai: http://localhost:4200
echo.
pause
exit /b 0

:RUN_BACKEND
cd /d "%~dp0backend"
title Backend - Spring Boot [Port 8080]
echo ========================================================
echo   KHOI DONG BACKEND - SPRING BOOT (PORT 8080)
echo ========================================================

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo [1/2] Phat hien tien trinh cu dang chiem cong 8080 [PID %%a], dang giai phong...
    taskkill /F /PID %%a /T >nul 2>&1
)

echo [2/2] Dang chay mvn spring-boot:run ...
echo       (Nhan Ctrl+C de dung Backend)
echo ========================================================
call mvn spring-boot:run

echo.
echo [THONG BAO] Backend Spring Boot da dung.
pause
exit /b 0

:RUN_FRONTEND
cd /d "%~dp0frontend"
title Frontend - Angular [Port 4200]
echo ========================================================
echo   KHOI DONG FRONTEND - ANGULAR (PORT 4200)
echo ========================================================

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":4200" ^| findstr "LISTENING"') do (
    echo [1/3] Phat hien tien trinh cu dang chiem cong 4200 [PID %%a], dang giai phong...
    taskkill /F /PID %%a /T >nul 2>&1
)

if not exist "node_modules" (
    echo [2/3] Chua co node_modules, dang chay npm install ...
    call npm install
    if errorlevel 1 (
        echo [LOI] npm install that bai. Vui long kiem tra Node.js / npm.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Da tim thay node_modules.
)

echo [3/3] Dang khoi chay Angular dev server (http://localhost:4200) ...
echo       (Nhan Ctrl+C de dung Frontend)
echo ========================================================
call npm start

echo.
echo [THONG BAO] Frontend Angular da dung.
pause
exit /b 0
