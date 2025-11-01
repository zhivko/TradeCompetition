@echo off
echo Starting Trading Competition Application...
echo.

echo Killing any existing Python processes running main.py or dashboard.py...
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| find "PID:"') do (
    taskkill /F /PID %%i >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat
echo.
echo Starting main.py in background...
start "Main Trading Process" cmd /c "call .venv\Scripts\activate.bat && python main.py %1"

echo Waiting for main.py to initialize...
timeout /t 3 /nobreak >nul

echo.
echo Starting dashboard.py...
call .venv\Scripts\activate.bat && python dashboard.py

echo.
echo Application started. Dashboard should be available at http://localhost:5000
pause