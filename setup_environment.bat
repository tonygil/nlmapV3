@echo off
REM Taxonomy Mapper V3.2 - Environment Setup
REM Run this once to set up the Python environment for all users

echo.
echo ========================================
echo   Taxonomy Mapper V3.2 - Setup
echo ========================================
echo.

REM Change to the directory where this batch file is located
cd /d "%~dp0"

REM Find Python
set PYTHON_CMD=

REM Check if python is in PATH
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :found_python
)

REM Check if py launcher is available
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :found_python
)

REM Check common locations
if exist "C:\Python314\python.exe" set PYTHON_CMD=C:\Python314\python.exe && goto :found_python
if exist "C:\Python312\python.exe" set PYTHON_CMD=C:\Python312\python.exe && goto :found_python
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe && goto :found_python
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe && goto :found_python

echo ERROR: Python not found. Please install Python 3.8 or higher first.
echo Download from: https://www.python.org/downloads/
pause
exit /b 1

:found_python
echo Found Python: %PYTHON_CMD%
echo.

REM Check if venv already exists
if exist "venv\Scripts\python.exe" (
    echo Virtual environment already exists.
    echo.
    set /p RECREATE="Do you want to recreate it? (y/N): "
    if /i not "%RECREATE%"=="y" (
        echo.
        echo Updating packages only...
        "venv\Scripts\pip.exe" install -r requirements.txt
        goto :done
    )
    echo Removing old virtual environment...
    rmdir /s /q venv
)

echo.
echo Creating virtual environment...
%PYTHON_CMD% -m venv venv

if not exist "venv\Scripts\python.exe" (
    echo.
    echo ERROR: Failed to create virtual environment.
    echo Make sure you have write permissions to this folder.
    pause
    exit /b 1
)

echo.
echo Installing required packages...
"venv\Scripts\pip.exe" install --upgrade pip
"venv\Scripts\pip.exe" install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install packages.
    pause
    exit /b 1
)

:done
echo.
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo You can now run: launch_gui.bat
echo.
echo All users on this server can use the application by
echo double-clicking launch_gui.bat - no Python installation
echo required on their machine.
echo.
pause
