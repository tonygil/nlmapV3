@echo off
REM NL Taxonomy Mapper V2 - GUI Launcher
REM Double-click this file to launch the GUI

echo.
echo ========================================
echo   NL Taxonomy Mapper V2 - GUI Launcher
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    echo.
    pause
    exit /b 1
)

echo Starting GUI application...
echo.

REM Launch the GUI
python taxonomy_matcher_gui.py

REM If there's an error, show it
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start the application
    echo.
    echo Possible solutions:
    echo 1. Install dependencies: pip install -r requirements.txt
    echo 2. Check if taxonomy_matcher_gui.py exists
    echo 3. Ensure input files are in the correct location
    echo.
    pause
)
