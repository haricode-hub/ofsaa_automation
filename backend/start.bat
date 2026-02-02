@echo off
echo Starting OFSAA Installation Backend...
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python main.py
pause