@echo off
rem Define a machine-isolated virtual environment folder using the workstation's hostname.
rem This prevents path corruption and sync conflicts across shared OneDrive workstations.
set VENV_DIR=env_%COMPUTERNAME%

rem Verify if the workstation-specific virtual environment is already initialized
if not exist "%VENV_DIR%\Scripts\activate" (
    echo "Initializing clean, machine-isolated Python environment for this workstation..."
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo Error: Failed to generate virtual environment. Ensure Python is installed and on your system PATH.
        pause
        exit /b 1
    )
    echo Updating environment tools and pip dependencies quietly...
    cmd /c "%VENV_DIR%\Scripts\pip install -q --upgrade pip && %VENV_DIR%\Scripts\pip install -q -r requirements.txt"
)

rem Activate the workstation-specific relative virtual environment
call %VENV_DIR%\Scripts\activate

echo "SSM-iCrop Environment Ready. Launching dashboard..."
streamlit run app/frontend/ui.py

rem Safety catch so the terminal window remains open on crash/exit
pause
