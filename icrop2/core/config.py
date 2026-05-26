import os

# Local OneDrive Reference Path for debugging sample models and weather files
LOCAL_ONEDRIVE_REF_PATH = r"F:\PersonalOD\OneDrive\8.ProjectLinhTinh\1. icrop\Sample Model\SSM-iCrop2"

# Database path (fully isolated v2)
DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "app_v2.db")
)
