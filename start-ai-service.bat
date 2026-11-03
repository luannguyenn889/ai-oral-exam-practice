@echo off
chcp 65001 >nul
if /I "%~1"=="--inline" (
    call "%~dp0ai-service\run-ai-service.bat"
    exit /b %errorlevel%
)

echo ========================================================
echo   Dang mo cua so Terminal chay FastAPI AI Service...
echo   - URL        : http://localhost:8000
echo   - Swagger UI : http://localhost:8000/docs
echo   (Goi y: Dung .\ai-service\run-ai-service.bat neu muon chay ngay trong terminal hien tai)
echo ========================================================
start "AI Service - FastAPI (Port 8000)" cmd /k ""%~dp0ai-service\run-ai-service.bat""
