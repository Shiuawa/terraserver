@echo off
rem Uso del desarrollador: genera terraserver\windows\app.exe
cd /d "%~dp0"
python -m pip install -r requirements-build.txt
python build-portable.py
pause
