@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto error
set /p APP_PASSWORD=Choose your workspace password (at least 16 characters): 
start "" http://127.0.0.1:5000
.venv\Scripts\python.exe app.py
pause
exit /b
:error
pause
