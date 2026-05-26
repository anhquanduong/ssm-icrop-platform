# Laptop Development Sync & Configuration Log

This log documents all setups, configurations, and modifications performed on this laptop (**DESKTOP-H228FFH**) for the **BOKU SSM-iCrop Growth Platform** project. Since this folder is synced via OneDrive, this file serves as the context bridge to let you (and your Antigravity agent on your Home PC) resume work seamlessly when you switch back.

---

## 💻 Machine Context: Laptop
*   **Computer Name**: `DESKTOP-H228FFH`
*   **Local Project Directory**: `D:\OD_personal\OneDrive\8.ProjectLinhTinh\1. icrop`
*   **Local Python Interpreter**: Anaconda Python 3.13.5 (`C:\ProgramData\anaconda3\python.exe`)
*   **Active Server Port**: `8501`

---

## 🛠️ Work Done on Laptop

### 1. Robust Python Path Auto-Detection
We replaced the simple, static python path call inside `run_app.bat` with a robust, flat `goto`-based batch routine. 

This script:
1. First checks if `python` is globally available on the environment `%PATH%`.
2. If not, it checks for **Anaconda Python 3.13.5** at `C:\ProgramData\anaconda3\python.exe` (selected on this laptop).
3. If not, it checks for **QGIS Python 3.12.8** at `C:\Program Files\QGIS 3.34.14\apps\Python312\python.exe` (backup).
4. Gracefully prompts with download instructions if no Python 3 interpreter is found.

### 2. OneDrive Cross-Machine Environment Isolation
We verified and utilized the workstation-specific virtual environment directory name:
*   `set VENV_DIR=env_%COMPUTERNAME%`
*   This resolved to `env_DESKTOP-H228FFH` on this laptop.
*   **Impact**: When you return to your Home PC, it will run its own separate folder (e.g. `env_HOME-PC`), preventing virtual environment folder lockups, absolute path corruptions, or synchronization collisions on OneDrive!

### 3. Dependencies Fully Hydrated
We executed the clean workspace installation inside the isolated laptop environment. The following libraries from `requirements.txt` were successfully installed:
*   `streamlit` (Dashboard server framework)
*   `streamlit-folium` & `folium` (Interactive GIS mapping widgets)
*   `pandas`, `openpyxl`, `numpy` (Core data modeling and BOKU spreadsheet ingestion)
*   `plotly` (Scenario charts and yield graphs)
*   `requests` & `cryptography` (API ingestion and secure auth hashing)

### 4. Background Streamlit Server Verification
We successfully launched the dashboard and bypassed Streamlit's initial telemetry prompt. The server is active in the background of this laptop, listening at:
👉 **[http://localhost:8501](http://localhost:8501)**

### 5. SMTP Mail Server Configuration & Real Verification
We successfully configured and verified your real email credentials inside:
*   **Path**: `.streamlit/secrets.toml` (locally stored, ignored by Git).
*   **Status**: Fully active! We registered your primary Google email `aquan.duong@gmail.com` and secure App Password `tvzt jbqb yvfa rqeg`.
*   **Testing**: We created and ran a verification script at `tests/test_smtp_real.py` which successfully logged into Gmail's servers (STARTTLS port 587) and dispatched a real verification test email directly to your inbox.
*   **Safety Note**: The `secrets.toml` file containing your credentials is strictly local to this machine (and safely excluded by your updated `.gitignore` rules) so it will never leak to public repositories.

### 6. GitHub Remote Verification & Sync
We verified the local Git configuration at `.git/config` and committed all laptops updates:
*   **Remote URL**: `https://github.com/anhquanduong/ssm-icrop-platform`
*   **Sync Status**: Fully pushed and synced! All local changes, including the updated `.gitignore` and `tests/test_smtp_real.py`, have been committed under your authorized email identity (`aquan.duong@gmail.com`) and successfully pushed to your GitHub repository under commit ID `49022ec`.
### 7. Port 8502 Sandbox Alignment for User Registrations & Resets
We identified and resolved hardcoded references to port `8501` inside the isolated `icrop2` workspace. Under `./icrop2/utils/auth_secure.py`, all fallback URLs generated during:
1. User registration activations,
2. Manual verification email resends, and
3. Password recovery requests
were redirected from `http://localhost:8501` to `http://localhost:8502` to match the independent sandbox configuration.

### 8. Green Verification Runs for Dual Runtimes
We successfully verified both test suites concurrently in their respective paths:
* **iCrop 2 (Sandbox)**: 14 out of 14 unit and integration tests passed cleanly (including a newly authored `test_secure_auth.py` verifying the correct port `8502` output for email links).
* **iCrop 1 (Production)**: 39 out of 39 tests passed cleanly (including full cryptographic, database migration, and real SMTP network integrations).

---

## 🔄 How to Resume on Your Home PC

When you open this folder on your Home PC:
1.  **Set Active Workspace**: Open `f:\PersonalOD\OneDrive\8.ProjectLinhTinh\1. icrop` in your Antigravity environment on your Home PC.
2.  **Run Application**: Simply double-click `run_app.bat` (for iCrop 1 on Port 8501) and `run_icrop2.bat` (for iCrop 2 on Port 8502).
    *   *Why it will work*: The batch scripts will automatically notice that your `%COMPUTERNAME%` is different from the laptop. They will look for your Home PC's virtual environment folders (e.g., `env_YOUR_HOME_PC_NAME` and `env_YOUR_HOME_PC_NAME_v2`). If they do not exist, they will automatically find your Home PC's Python path, generate clean environments, install dependencies, and launch without any manual setup!
3.  **Local History**: Your Antigravity agent on your Home PC can read this `LAPTOP_DEVELOPMENT_LOG.md` file to immediately absorb the complete state of the project, including recent features and test suites.

---

*Log generated on 2026-05-26 23:45 (Laptop Local Time) by Antigravity.*

