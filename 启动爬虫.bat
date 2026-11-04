@echo off
rem Change to the folder where this .bat file is located (%~dp0 = this file's directory)
cd /d "%~dp0"

rem Check that Python is installed (pythonw = runs without a black console window)
where pythonw >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python and check "Add Python to PATH".
    pause
    exit /b 1
)

rem Launch the GUI without showing a console window
start "" pythonw gui.py
