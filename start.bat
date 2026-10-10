@echo off
cd /d "%~dp0"
start "NOVIQO backend" cmd /k "call .venv\Scripts\activate && cd backend && uvicorn app.main:app --reload"
start "NOVIQO frontend" cmd /k "cd frontend && npm run dev"
echo Backend:  http://localhost:8000/docs
echo App:      http://localhost:5173   (use Chrome or Edge)
