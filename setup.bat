@echo off
rem One-time setup on Windows. Needs Python 3.12 or newer (python.org, tick "Add python.exe to PATH") and Node.js LTS.
cd /d "%~dp0"
py -3 --version >nul 2>&1 || (echo Python was not found. Install it from python.org and tick "Add python.exe to PATH", then run this again. & exit /b 1)
py -3 -m venv .venv || goto :err
call .venv\Scripts\activate || goto :err
python -m pip install --upgrade pip || goto :err
pip install -r backend\requirements.txt pytest || goto :err
cd frontend && call npm install || goto :err
cd ..
rem local settings: same as .env.example but without DATABASE_URL, so a local SQLite file is used (no Docker needed)
if not exist backend\.env findstr /v /b /c:"DATABASE_URL=" .env.example > backend\.env
echo.
echo Setup finished. Now open backend\.env in Notepad and set LLM_PROVIDER and your API key, then run start.bat
exit /b 0
:err
echo.
echo Setup failed - copy the error above and send it over.
exit /b 1
