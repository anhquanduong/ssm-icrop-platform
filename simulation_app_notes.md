Here is a clean, organized, and professionally structured Markdown log of our entire conversation. You can save this text directly into a `.md` file (e.g., `simulation_app_notes.md`) inside your OneDrive folder so you can quickly reference these development blueprints, prompts, and debugging steps from either your office laptop or home PC!

---

# 📑 SSM-iCrop Platform Development Log & Architecture Ledger

## 🗺️ 1. Ingesting Spatial Soil Baselines (ISRIC Integration)

To prevent your point-based simulation from relying strictly on blind user guesses, we designed a **Smart Default** fallback system that automatically fetches real global digital soil data when a user interacts with the frontend map.

### The Antigravity Ingestion Core Prompt

```text
System/Agent Task: Implement ISRIC SoilGrids REST API Integration to Auto-Populate UI Soil Forms

Context:
- Source Endpoint: `https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&properties=bdod,soc,clay,sand`
- Files to Modify: `/app/core/soil_api.py` (New file) and integration into `/app/frontend/ui.py`

Objective:
Act as a Principal Geospatial Data Engineer and Agronomic Architect. Your task is to write an automated data ingestion utility that queries the ISRIC SoilGrids 250m global database using coordinates captured from map clicks. The returned soil texture variables must be converted via pedotransfer pedological functions into simulation-ready properties (PAWC, SOM) and injected automatically into the Streamlit session state form fields as dynamic baselines.

Execute the following implementation steps:

1. BUILD THE ISRIC CONSUMER CORE (`/app/core/soil_api.py`)
   - Implement a function `fetch_isric_soil_data(lat, lon)` using a resilient `requests.Session()` with a 5-second connection timeout.
   - Parse the returning nested JSON response payload to extract mean values across the 0-30cm depth layers for:
     * `soc` (Soil Organic Carbon in dg/kg -> convert to Soil Organic Matter percentage: SOM% = (SOC/100) * 1.724).
     * `clay` and `sand` mass fractions (g/kg).
   - Apply a standard pedotransfer approximation formula to calculate Plant Available Water Capacity (PAWC) from the sand and clay fractions:
     PAWC (mm/m) ≈ 200 - (1.5 * Sand%) + (0.5 * Clay%).
   - Return a dictionary containing calculated values for `som`, `pawc`, and a predicted baseline `root_zone_depth` (defaulting to 1000mm if no bedrock constraint is found).

2. ASYNCHRONOUS UI FORM BINDING (`/app/frontend/ui.py`)
   - Modify your existing map click action loop block. When `map_data["last_clicked"]` registers a change, intercept the thread state:
     ```python
     with st.spinner("Fetching global ISRIC SoilGrids grid profile characteristics..."):
         isric_profile = fetch_isric_soil_data(new_lat, new_lon)
         if isric_profile:
             st.session_state["som_key"] = isric_profile["som"]
             st.session_state["pawc_key"] = isric_profile["pawc"]
             st.session_state["depth_key"] = isric_profile["root_zone_depth"]
     ```

3. FORM PARAMETER SYNCHRONIZATION
   - Update your manual entry soil configuration input fields (`st.number_input`) to bind directly to these keys (`key="som_key"`, `key="pawc_key"`, `key="depth_key"`).
   - This ensures that when a user pans to Hanoi or Vienna and clicks, the numbers instantly jump to match the real-world physical soil properties of that location, while still allowing the user to type over them if they possess better physical soil core sample measurements.

Output the complete Python code for soil_api.py and the structural layout updates for ui.py.

```

---

## 🎛️ 2. Environmental Controls & Multi-Scenario Fidelity

To support controlled scientific experiments, we updated the management inputs to boot up with a clean slate (**0 default rounds**) and structured an **Engine Selector Switch** to run both potential and stress-limited execution routines.

### The Antigravity Advanced Process Toggle Prompt

```text
System/Agent Task: Refactor Advanced Engine Core with Optional Modular Biophysical Sub-Models (VPD, Leaching, Root Growth, Heat Shock)

Context:
- Primary Targets: `/app/core/model_engine.py` (Simulation Equations) and `/app/frontend/ui.py` (Interface Switches)
- Target Sub-Models to Add: 1. Vapor Pressure Deficit (VPD), 2. Nitrogen Leaching via Drainage, 3. Dynamic Root Zone Growth, 4. Pollination Heat Shock.

Objective:
Act as a Lead Computational Agronomist and Systems Architect. Your task is to upgrade the application to support an interactive modular simulation framework. When 'Advanced Agro-Climate Mode' is active, the UI must reveal independent checkbox switches for each of the 4 advanced sub-models. The core backend engine must accept these boolean configurations and dynamically execute their respective physical/physiological stress equations inside the daily simulation loop.

Execute the following implementation steps:

1. COMPONENT CODES FOR CONFIGURATION UI (`/app/frontend/ui.py`)
   - Inside the Advanced Model conditional block, add an elegant `st.expander("🛠️ Advanced Biophysical Process Selectors", expanded=True)`.
   - Implement 4 distinct, clean checkbox toggles and store them as a configurations dictionary:
     * `use_vpd = st.checkbox("💨 Enable Vapor Pressure Deficit (VPD) Atmospheric Stress", value=True)`
     * `use_leaching = st.checkbox("🌧️ Enable Nitrogen Leaching via Excess Drainage", value=True)`
     * `use_root_growth = st.checkbox("🌱 Enable Dynamic Root Zone Expansion (Phased Growth)", value=True)`
     * `use_heat_shock = st.checkbox("🔥 Enable Pollination Heat Shock & Sterility Index", value=True)`
   - Bundle these booleans into an `advanced_options` map and pass it directly to the engine initializer: `SSMiCropEngine(..., mode="Advanced", advanced_options=advanced_options)`.

2. REFACTOR MATHEMATICAL BACKEND ENGINE (`/app/core/model_engine.py`)
   Update the daily simulation iteration step to handle the sub-model switches explicitly:
   - **Sub-Model 1: VPD Atmospheric Demand Check** (Modulates Radiation Use Efficiency ($RUE$) and dynamically increases the critical $FTSW$ moisture threshold based on daily air dryness).
   - **Sub-Model 2: Nitrogen Leaching via Water Drainage** (Calculates proportional chemical washout of the active mineral Nitrogen pool following deep gravitational drainage: $\Delta N_{\text{leached}} = N_{\text{available}} \times (DRAIN / \text{Storage\_Capacity})$).
   - **Sub-Model 3: Dynamic Phased Root Zone Penetration** (Increases rooted footprint depth linearly or sigmoidally driven by accumulated thermal time ($\sum^\circ\text{Cd}$) from emergence until flowering).
   - **Sub-Model 4: Pollination Heat Shock & Sterility** (Monitors $T_{\max} > 35^\circ\text{C}$ during the critical anthesis flowering window, accumulating a sterility penalty that directly suppresses final Harvest Index ($HI$) rather than vegetative mass).

Output the complete, fully audited Python code refactoring blocks for model_engine.py and the structural UI updates for ui.py.

```

---

## 🛠️ 3. Core Engine Debugging Ledger

### Bug 1: Flatlined Biomass Curve (`0.01 t/ha`)

* **Root Cause:** A raw dataset unit mismatch where solar radiation (`SRAD`) was ingested in Watt-hours or Kilojoules instead of **Megajoules per square meter ($MJ/m^2/day$)**, effectively trapping the crop loop in pitch-black conditions.
* **Resolution Rule:** Apply an immediate conditional parser scaling module check:

$$\text{SRAD}_{\text{MJ}} = \text{SRAD}_{\text{Wh}} \times 0.0036$$



### Bug 2: Grain Yield Stalling Below reference Boundaries (`0.17 t/ha`)

* **Root Cause:** A phenology trigger failure where the calculation engine failed to smoothly execute the transition from vegetative structural matter partitioning over to reproductive grain-filling.
* **Resolution Rule:** Rewrote the state handler to inherit the true source-sink remobilization metrics and stage duration benchmarks (`bdSOWEMR = 3`, `bdEMREJU = 8.5`, `bdSILPM = 33.8`) extracted directly from the reference workbook **`SSM_Maize_REF.xlsm`**.

---

## 💻 4. Cross-Platform OneDrive Workflow Automation

To prevent path conflicts and broken virtual environments when alternating between your **office laptop** and **home PC**, we isolated the local Python engine runtimes while keeping the core codebase shared via cloud synchronization.

### Root Folder Bootstrap Controller (`/run_app.bat`)

Create a file named `run_app.bat` directly in your root project folder. It will automatically initialize separate virtual environment folders (`env_local`) on each machine:

```batch
@echo off
if not exist env_local\Scripts\activate (
    echo "Initializing clean, machine-isolated Python environment for this workstation..."
    python -m venv env_local
    cmd /c "env_local\Scripts\pip install -q --upgrade pip && env_local\Scripts\pip install -q -r requirements.txt"
)
call env_local\Scripts\activate
echo "SSM-iCrop Environment Ready. Launching dashboard..."
streamlit run app/frontend/ui.py
pause

```

---

## 🌐 5. Deployment Checklist: Streamlit Community Cloud

### The Clean `.gitignore` Manifest

Save this text file in the root folder to protect your private data and local environments from being pushed onto GitHub:

```text
env_local/
.venv/
env/
__pycache__/
*.pyc
app.db
production_backup.db
.DS_Store
Thumbs.db

```

### The Pinned `requirements.txt` Dependency Grid

```text
streamlit
streamlit-folium
folium
pandas
openpyxl
plotly
requests
cryptography

```

### Resolving Module and Encoding Errors

1. **`ModuleNotFoundError: No module named 'cryptography'`**
* *Cause:* Streamlit Cloud defaulted to an experimental Python 3.14 instance where pre-compiled wheels for security frameworks did not exist.
* *Fix:* Re-deployed the app via the Streamlit dashboard workspace and manually forced the runtime container to a stable **Python 3.11** anchor.


2. **`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff`**
* *Cause:* Windows Notepad automatically appended a hidden Byte Order Mark (BOM) to config files.
* *Fix:* Purged the file from the repository and managed configurations through the interactive Streamlit Settings interface instead.



---

## 📧 6. Secure Email Validation (SMTP Over TLS Pipeline)

To manage user access safely for your colleagues, route tokens securely through Google's mail relay network without hardcoding plaintext credentials into your codebase.

### Secure In-Memory Environment Storage (`Streamlit Secrets Dashboard`)

```toml
[gmail_credentials]
sender = "your_allocated_email@gmail.com"
app_password = "abcdefghijklmnop"  # 16-character Google App Token with spaces stripped out

```

### The Cloud-Safe Mail Utility (`/app/utils/email_verify.py`)

```python
import smtplib
import random
import streamlit as st
from email.mime.text import MIMEText

def send_verification_code(recipient_email: str) -> int:
    verification_code = random.randint(100000, 999999)
    
    # Securely retrieve tokens directly from encrypted container memory
    sender_email = st.secrets["gmail_credentials"]["sender"]
    app_password = st.secrets["gmail_credentials"]["app_password"]
    
    msg = MIMEText(f"Hello,\n\nYour testing access verification token for the SSM-iCrop Platform is: {verification_code}")
    msg["Subject"] = "SSM-iCrop Platform Verification Token"
    msg["From"] = sender_email
    msg["To"] = recipient_email
    
    try:
        # Use Port 587 (STARTTLS) to smoothly bypass strict public cloud email firewalls
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        return verification_code
    except Exception as e:
        st.error(f"Mail Delivery System Failure: {e}")
        return None

```