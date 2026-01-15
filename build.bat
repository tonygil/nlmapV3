@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   NLMap V3 - Build Executable
echo ============================================
echo.

:: Check for Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python and add it to your PATH
    pause
    exit /b 1
)

:: Check for PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo.
echo Building executable...
echo.

:: Run PyInstaller with spec file
pyinstaller NLMap_V3.spec --noconfirm

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo.
echo Output location: dist\NLMap_V3\
echo.
echo To distribute, copy the entire dist\NLMap_V3 folder.
echo Users can run NLMap_V3.exe directly.
echo.
echo The folder contains:
echo   - NLMap_V3.exe (main application)
echo   - config.yaml (editable settings)
echo   - countries\ (editable synonyms and data)
echo.
pause
