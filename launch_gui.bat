@echo off
REM Taxonomy Mapper V3.2 - GUI Launcher
REM Double-click this file to launch the GUI

echo.
echo ========================================
echo   Taxonomy Mapper V3.2 - GUI Launcher
echo ========================================
echo.

REM Change to the directory where this batch file is located
cd /d "%~dp0"

REM Check for virtual environment first (recommended for multi-user)
if exist "venv\Scripts\python.exe" (
    echo Using bundled virtual environment...
    "venv\Scripts\python.exe" taxonomy_matcher_gui.py
    goto :check_error
)

REM Try to find Python if no venv
set PYTHON_CMD=

REM Check if python is in PATH
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :found_python
)

REM Check if py launcher is available (Windows Python Launcher)
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :found_python
)

REM Check common Python installation locations
if exist "C:\Python314\python.exe" (
    set PYTHON_CMD=C:\Python314\python.exe
    goto :found_python
)
if exist "C:\Python312\python.exe" (
    set PYTHON_CMD=C:\Python312\python.exe
    goto :found_python
)
if exist "C:\Python311\python.exe" (
    set PYTHON_CMD=C:\Python311\python.exe
    goto :found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
    goto :found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    goto :found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    goto :found_python
)

REM Python not found - show helpful error message
echo.
echo ============================================================
echo   ERROR: Python was not found on this computer
echo ============================================================
echo.
echo This application requires Python 3.8 or higher to run.
echo.
echo TO FIX THIS (Admin required):
echo.
echo   1. Run setup_environment.bat as Administrator
echo      (This creates a bundled Python environment)
echo.
echo   OR install Python manually:
echo.
echo   1. Download Python from: https://www.python.org/downloads/
echo   2. During installation, check: [x] "Add Python to PATH"
echo   3. After installing, run setup_environment.bat
echo.
echo ============================================================
echo.
pause
exit /b 1

:found_python
echo Found Python: %PYTHON_CMD%
echo Starting GUI application...
echo.

REM Check if required file exists
if not exist "taxonomy_matcher_gui.py" (
    echo.
    echo ERROR: taxonomy_matcher_gui.py not found!
    echo.
    echo Make sure you're running this from the correct folder.
    echo Current folder: %CD%
    echo.
    pause
    exit /b 1
)

REM Launch the GUI
%PYTHON_CMD% taxonomy_matcher_gui.py

:check_error
REM If there's an error, show it
if errorlevel 1 (
    echo.
    echo ============================================================
    echo   ERROR: Failed to start the application
    echo ============================================================
    echo.
    echo This usually means some Python packages are missing.
    echo.
    echo TO FIX THIS:
    echo.
    echo   Run: setup_environment.bat
    echo.
    echo   This will install all required packages.
    echo.
    echo If you still have issues, contact support.
    echo.
    pause
)
