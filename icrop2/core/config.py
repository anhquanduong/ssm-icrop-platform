import os

# Database path (fully isolated v2)
DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "app_v2.db")
)

# Absolute OneDrive paths for local debugging (Potential vs Advanced/Nitrogen tracks)
PATH_ORIGINAL_SSM = r"F:\PersonalOD\OneDrive\8.ProjectLinhTinh\1. icrop\Sample Model\SSM-iCrop2"
PATH_ADVANCED_SSM = r"F:\PersonalOD\OneDrive\8.ProjectLinhTinh\1. icrop\Sample Model\SSM-iCrop2N"

# Fallback relative paths for Cloud compatibility (Streamlit Community Cloud / Docker runs)
FALLBACK_ORIGINAL_SSM = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "baseline"))
FALLBACK_ADVANCED_SSM = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "advanced"))
