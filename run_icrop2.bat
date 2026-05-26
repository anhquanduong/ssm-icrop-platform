@echo off
rem Define a machine-isolated virtual environment folder using the workstation's hostname.
set VENV_DIR=env_%COMPUTERNAME%_v2

rem Dynamic Python Path Resolution
set PYTHON_CMD=

rem 1. Check if global python is functional and not a dummy Microsoft Store execution alias (ignoring WindowsApps)
where python >nul 2>nul
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        echo %%i | findstr /i "WindowsApps" >nul
        if errorlevel 1 (
            set PYTHON_CMD="%%i"
            goto :PYTHON_FOUND
        )
    )
)

rem 2. Check for local uv-managed Python interpreters dynamically
if exist "C:\Users\%USERNAME%\AppData\Roaming\uv\python" (
    for /d %%d in ("C:\Users\%USERNAME%\AppData\Roaming\uv\python\*") do (
        if exist "%%d\python.exe" (
            echo uv-managed Python installation detected: %%d\python.exe
            set PYTHON_CMD="%%d\python.exe"
            goto :PYTHON_FOUND
        )
    )
)

rem 3. Check for standard local user Python installations dynamically
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python" (
    for /d %%d in ("C:\Users\%USERNAME%\AppData\Local\Programs\Python\*") do (
        if exist "%%d\python.exe" (
            echo User-profile Python installation detected: %%d\python.exe
            set PYTHON_CMD="%%d\python.exe"
            goto :PYTHON_FOUND
        )
    )
)

rem 4. Check for standard Anaconda system paths
if exist "C:\ProgramData\anaconda3\python.exe" (
    echo System Anaconda Python installation detected: C:\ProgramData\anaconda3\python.exe
    set PYTHON_CMD="C:\ProgramData\anaconda3\python.exe"
    goto :PYTHON_FOUND
)
if exist "C:\Users\%USERNAME%\anaconda3\python.exe" (
    echo User Anaconda Python installation detected: C:\Users\%USERNAME%\anaconda3\python.exe
    set PYTHON_CMD="C:\Users\%USERNAME%\anaconda3\python.exe"
    goto :PYTHON_FOUND
)

rem 5. Check for standard system Program Files Python installations dynamically
if exist "C:\Program Files\Python" (
    for /d %%d in ("C:\Program Files\Python\*") do (
        if exist "%%d\python.exe" (
            echo System Python installation detected: %%d\python.exe
            set PYTHON_CMD="%%d\python.exe"
            goto :PYTHON_FOUND
        )
    )
)

rem 6. Check for standard QGIS apps backup paths dynamically
if exist "C:\Program Files\QGIS" (
    for /d %%d in ("C:\Program Files\QGIS\*") do (
        if exist "%%d\apps\Python312\python.exe" (
            echo QGIS Python installation detected: %%d\apps\Python312\python.exe
            set PYTHON_CMD="%%d\apps\Python312\python.exe"
            goto :PYTHON_FOUND
        )
        if exist "%%d\apps\Python311\python.exe" (
            echo QGIS Python installation detected: %%d\apps\Python311\python.exe
            set PYTHON_CMD="%%d\apps\Python311\python.exe"
            goto :PYTHON_FOUND
        )
    )
)

echo Error: Python was not found on your system PATH or in standard paths.
echo Please download and install Python 3.x from python.org or Anaconda.
pause
exit /b 1

:PYTHON_FOUND
cd icrop2
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
cmd /c "%VENV_DIR%\Scripts\pip install -q --upgrade pip && %VENV_DIR%\Scripts\pip install -q -r requirements_v2.txt"

:ACTIVATE_ENV
rem Activate the workstation-specific relative virtual environment
call %VENV_DIR%\Scripts\activate

echo Checking/installing dependencies from requirements_v2.txt...
pip install -q -r requirements_v2.txt

echo "SSM-iCrop2 Environment Ready. Launching dashboard on port 8502..."
streamlit run frontend/ui.py --server.port 8502

rem Safety catch so the terminal window remains open on crash/exit
pause

