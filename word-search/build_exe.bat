@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem בונה את אשף ההתקנה dist\HebDocSearch-Setup-*.exe (נדרש Inno Setup 6)
if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv
)
.venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.venv\Scripts\python packaging\build.py
pause
