@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv
)
.venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.venv\Scripts\pyinstaller --noconfirm --windowed --name HebWordSearch --hidden-import win32com.client --hidden-import pythoncom main.py
echo.
echo Done: dist\HebWordSearch\HebWordSearch.exe
pause
