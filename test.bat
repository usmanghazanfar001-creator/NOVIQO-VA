@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
set PYTHONPATH=.
pytest -q tests
