import re
import io
import os
import pandas as pd
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

def extract_coords_from_text(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Extracts latitude and longitude coordinates from a line of text or cell grid
    using robust regular expressions matching BOKU metadata styles.
    
    Examples matched:
      - "LAT (o): 32.67", "LON (o): 51.87"
      - "LAT=17.88", "LONG=78.45"
      - "LAT (deg): 48.283", "LON (deg): 16.467"
      - "LATITUDE: 48.283", "LONGITUDE: 16.467"
    """
    # Latitude regex matching: "lat", "lat(o)", "lat(deg)", "latitude" followed by spaces/punctuation, then a float
    lat_match = re.search(
        r'\b(?:lat|latitude)\b[^0-9.-]*([-+]?\d*\.\d+|\b[-+]?\d+\b)', 
        text, 
        re.IGNORECASE
    )
    
    # Longitude regex matching: "lon", "long", "lon(o)", "longitude" followed by spaces/punctuation, then a float
    lon_match = re.search(
        r'\b(?:lon|long|longitude)\b[^0-9.-]*([-+]?\d*\.\d+|\b[-+]?\d+\b)', 
        text, 
        re.IGNORECASE
    )
    
    extracted_lat = float(lat_match.group(1)) if lat_match else None
    extracted_lon = float(lon_match.group(1)) if lon_match else None
    
    return extracted_lat, extracted_lon

def is_header_row(row_cells: list) -> bool:
    """
    Identifies if a spreadsheet row represents the core SSM column header
    by searching for all five mandatory variables.
    """
    required = {"doy", "tmax", "tmin", "srad", "rain"}
    
    # Lowercase string conversions
    row_strings = [str(c).lower().strip() for c in row_cells if c is not None]
    
    # Count variables matching the target headers
    matches = 0
    for req in required:
        if any(req in cell for cell in row_strings):
            matches += 1
            
    return matches == 5

def parse_ssm_weather_file(file_wrapper) -> Tuple[pd.DataFrame, Optional[float], Optional[float]]:
    """
    Parses a BOKU SSM formatted weather file (Excel or whitespace-delimited text).
    Acccommodates multi-row descriptive metadata headers dynamically, extracts
    geospatial parameters, and sanitizes the output meteorological matrix.
    
    Parameters:
        file_wrapper: String file-path, BytesIO stream, or Streamlit UploadedFile.
        
    Returns:
        Tuple[pd.DataFrame, float, float]: 
            - Cleaned daily weather DataFrame [DOY, TMAX, TMIN, SRAD, RAIN]
            - Extracted Latitude (or None)
            - Extracted Longitude (or None)
    """
    # 1. Read file bytes and identify type
    filename = ""
    if isinstance(file_wrapper, str):
        filename = file_wrapper
        with open(file_wrapper, 'rb') as f:
            file_bytes = f.read()
    else:
        filename = getattr(file_wrapper, "name", "") or getattr(file_wrapper, "filename", "") or ""
        # Check seek cursor
        if hasattr(file_wrapper, "seek"):
            file_wrapper.seek(0)
        file_bytes = file_wrapper.read()
        if hasattr(file_wrapper, "seek"):
            file_wrapper.seek(0)
            
    # Detect file type
    is_excel = False
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.xls', '.xlsx', '.xlsm']:
            is_excel = True
            
    # Magic bytes fallback signature checks (PK.. for .xlsx or OLE2 for .xls)
    if not is_excel and file_bytes:
        if file_bytes.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1') or file_bytes.startswith(b'\x50\x4b\x03\x04'):
            is_excel = True
            
    # 2. Extract metadata & dynamic header row index by scanning the first 15 lines
    extracted_lat = None
    extracted_lon = None
    header_idx = None
    rows = []
    
    if is_excel:
        try:
            # Load first 15 rows of the workbook to inspect header and metadata
            df_preview = pd.read_excel(io.BytesIO(file_bytes), nrows=15, header=None)
            for _, row in df_preview.iterrows():
                row_vals = [cell if pd.notnull(cell) else "" for cell in row]
                rows.append(row_vals)
        except Exception as e:
            logger.error(f"Excel metadata inspection failed: {e}")
            raise ValueError(f"Unable to read Excel file headers: {str(e)}")
    else:
        # Read text file line by line
        try:
            text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = file_bytes.decode('latin-1')
            
        lines = text.splitlines()[:15]
        for line in lines:
            # Tokenize line by whitespace
            tokens = line.strip().split()
            rows.append(tokens)
            
    # Scan extracted rows
    for idx, row in enumerate(rows):
        # Join row cells to search for coordinates in metadata
        row_str = " ".join([str(c) for c in row if c != ""])
        
        lat_val, lon_val = extract_coords_from_text(row_str)
        if lat_val is not None and extracted_lat is None:
            extracted_lat = lat_val
            logger.info(f"Extracted Latitude from metadata: {extracted_lat}")
        if lon_val is not None and extracted_lon is None:
            extracted_lon = lon_val
            logger.info(f"Extracted Longitude from metadata: {extracted_lon}")
            
        # Detect true header row
        if is_header_row(row) and header_idx is None:
            header_idx = idx
            logger.info(f"Dynamically detected SSM weather column header at Row {idx}")
            
    if header_idx is None:
        raise ValueError(
            "Could not identify the true header row containing DOY, TMAX, TMIN, SRAD, and RAIN. "
            "Please check file structure and ensure mandatory parameters exist."
        )
        
    # 3. Read the full dataset from the true header offset
    try:
        if is_excel:
            df = pd.read_excel(io.BytesIO(file_bytes), skiprows=header_idx)
        else:
            # Dynamically determine separator based on comma presence in headers or data
            text_preview = file_bytes.decode('utf-8', errors='ignore')
            lines = text_preview.splitlines()
            header_line = lines[header_idx] if len(lines) > header_idx else ""
            if ',' in header_line:
                df = pd.read_csv(io.BytesIO(file_bytes), skiprows=header_idx, sep=',')
            else:
                # whitespace separation
                df = pd.read_csv(io.BytesIO(file_bytes), skiprows=header_idx, sep=r'\s+', engine='python')
    except Exception as e:
        logger.error(f"Failed to read dataset array at row index {header_idx}: {e}")
        raise RuntimeError(f"Failed to parse weather dataset: {str(e)}")
        
    # 4. Sanitize and structure the data frame
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Try to find a YEAR column
    year_col = None
    for col in df.columns:
        if col in ['YEAR', 'YEARS', 'YR']:
            year_col = col
            break
            
    # If YEAR is found, rename it to 'YEAR', otherwise try parsing DATE column, else default to 2025
    if year_col:
        df = df.rename(columns={year_col: 'YEAR'})
        df['YEAR'] = pd.to_numeric(df['YEAR'], errors='coerce').fillna(2025).astype(int)
    elif 'DATE' in df.columns:
        try:
            df['YEAR'] = pd.to_datetime(df['DATE']).dt.year
        except Exception:
            df['YEAR'] = 2025
    else:
        df['YEAR'] = 2025
        
    required_cols = ['YEAR', 'DOY', 'TMAX', 'TMIN', 'SRAD', 'RAIN']
    for col in required_cols:
        # Check if column is represented in current dataframe (exclude YEAR as we handled it)
        if col == 'YEAR':
            continue
        if col not in df.columns:
            # Try to resolve case-insensitive mappings
            matched_col = None
            for c in df.columns:
                if col == c.upper():
                    matched_col = c
                    break
            if matched_col:
                df = df.rename(columns={matched_col: col})
            else:
                raise ValueError(f"Required weather parameter '{col}' is missing in file.")
                
        # Force numeric conversions, turning trailing spaces/strings into NaN safely
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    # Clean rows with missing values in required parameters
    df = df.dropna(subset=required_cols)
    
    # Cast integers and floats
    df['YEAR'] = df['YEAR'].astype(int)
    df['DOY'] = df['DOY'].astype(int)
    for col in ['TMAX', 'TMIN', 'SRAD', 'RAIN']:
        df[col] = df[col].astype(float)

    # -----------------------------------------------------------------
    # SRAD UNIT AUTO-DETECTION AND SCALING
    # SSM/BOKU files store SRAD in kJ/m²/day (typical range 2000-25000).
    # Open-Meteo API returns MJ/m²/day (typical range 5-35).
    # Detect unit by inspecting the 95th percentile of the SRAD column:
    #   > 200  → likely kJ/m²/day   → divide by 1000
    #   40-200 → check for Wh/m²    → multiply by 0.0036
    #   5-40   → already MJ/m²/day  → no conversion needed
    # -----------------------------------------------------------------
    srad_p95 = df['SRAD'].quantile(0.95)
    if srad_p95 > 200.0:
        # kJ/m²/day detected — convert to MJ/m²/day
        df['SRAD'] = df['SRAD'] / 1000.0
        logger.info(
            f"SRAD auto-converted from kJ/m²/day to MJ/m²/day "
            f"(detected 95th-pct value: {srad_p95:.1f} kJ/m²/day)."
        )
    elif srad_p95 > 40.0:
        # Wh/m²/day detected — convert to MJ/m²/day (1 Wh = 0.0036 MJ)
        df['SRAD'] = df['SRAD'] * 0.0036
        logger.info(
            f"SRAD auto-converted from Wh/m²/day to MJ/m²/day "
            f"(detected 95th-pct value: {srad_p95:.1f} Wh/m²/day)."
        )
    else:
        logger.info(
            f"SRAD values appear to be in MJ/m²/day already "
            f"(95th-pct: {srad_p95:.2f} MJ/m²/day). No conversion applied."
        )

    # Final safety clamp: physical radiation range is 0 to 50 MJ/m²/day
    df['SRAD'] = df['SRAD'].clip(lower=0.0, upper=50.0)

    # Drop peripheral columns (like RH or WIND)
    final_df = df[required_cols].copy().reset_index(drop=True)
    logger.info(f"SSM Weather file parsed successfully. Extracted {len(final_df)} daily records.")

    return final_df, extracted_lat, extracted_lon

class WeatherProcessor:
    """
    Class wrapper for BOKU SSM weather file parsing and sanitization workflows.
    Provides clean static access for compatibility with frontend and backend routers.
    """
    @staticmethod
    def parse_ssm_weather_file(file_wrapper) -> Tuple[pd.DataFrame, Optional[float], Optional[float]]:
        return parse_ssm_weather_file(file_wrapper)
