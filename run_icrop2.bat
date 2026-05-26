@echo off
cd icrop2
if not exist .venv2 (
    echo Creating isolated virtual environment .venv2...
    python -m venv .venv2
)
call .venv2\Scripts\activate
pip install -r requirements_v2.txt
streamlit run frontend/ui.py --server.port 8502
pause
