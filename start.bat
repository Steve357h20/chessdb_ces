@echo off
chcp 65001 >nul
echo Starting ChessDB...
echo.

set "SCRIPT_DIR=%~dp0"

start "ChessDB Backend" cmd /k "cd /d "%SCRIPT_DIR%backend" && .\venv\Scripts\activate.bat && set FLASK_APP=app && flask run --port 5000"

timeout /t 2 /nobreak >nul

start "ChessDB Frontend" cmd /k "cd /d "%SCRIPT_DIR%frontend" && npm run dev"

echo.
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:3000
echo.
echo You can close this window. Servers run in separate windows.
pause
