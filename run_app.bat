@echo off
rem Define a machine-isolated virtual environment folder using the workstation's hostname.
rem This prevents path corruption and sync conflicts across shared OneDrive workstations.
set VENV_DIR=env_%COMPUTERNAME%

rem Dynamic Python Path Resolution
where python >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :PYTHON_FOUND
)

if exist "C:\ProgramData\anaconda3\python.exe" (
    echo Anaconda Python installation detected. Routing initialization...
    set PYTHON_CMD="C:\ProgramData\anaconda3\python.exe"
    goto :PYTHON_FOUND
)

if exist "C:\Program Files\QGIS 3.34.14\apps\Python312\python.exe" (
    echo QGIS Python installation detected. Routing initialization...
    set PYTHON_CMD="C:\Program Files\QGIS 3.34.14\apps\Python312\python.exe"
    goto :PYTHON_FOUND
)

echo Error: Python was not found on your system PATH or in standard paths.
echo Please download and install Python 3.x from python.org or Anaconda.
pause
exit /b 1

:PYTHON_FOUND
rem Verify if the workstation-specific virtual environment is already initialized
if exist "%VENV_DIR%\Scripts\activate.bat" goto :ACTIVATE_ENV
if exist "%VENV_DIR%\Scripts\activate" goto :ACTIVATE_ENV

echo Initializing clean, machine-isolated Python environment for this workstation (%VENV_DIR%)...
%PYTHON_CMD% -m venv %VENV_DIR%
if errorlevel 1 (
    echo Error: Failed to generate virtual environment. Ensure Python is installed.
    pause
    exit /b 1
)

echo Updating environment tools and pip dependencies quietly...
cmd /c "%VENV_DIR%\Scripts\pip install -q --upgrade pip && %VENV_DIR%\Scripts\pip install -q -r requirements.txt"

:ACTIVATE_ENV
rem Activate the workstation-specific relative virtual environment
call %VENV_DIR%\Scripts\activate

echo Checking/installing dependencies from requirements.txt...
pip install -q -r requirements.txt

echo "SSM-iCrop Environment Ready. Launching dashboard..."
streamlit run app/frontend/ui.py

rem Safety catch so the terminal window remains open on crash/exit
pause


