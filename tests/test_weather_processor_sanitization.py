import unittest
import pandas as pd
import numpy as np
import io
from app.utils.weather_processor import parse_ssm_weather_file

class TestWeatherProcessorSanitization(unittest.TestCase):
    """
    Test suite verifying robust header mapping variations and biophysical bounds 
    outlier linear interpolation inside the weather processor.
    """

    def test_header_coercion(self):
        """
        Verify that custom header variations are dynamically mapped to canonical headers.
        """
        # Create a CSV mock text with non-standard headers
        csv_data = """LAT (deg): 48.283 LON (deg): 16.467
years,day_of_year,temp_max,temp_min,solar_rad,precipitation
2025,1,15.0,5.0,12.0,0.0
2025,2,16.0,6.0,13.0,1.0
2025,3,17.0,7.0,14.0,2.0
"""
        file_wrapper = io.BytesIO(csv_data.encode('utf-8'))
        file_wrapper.name = "mock_weather.csv"
        
        df, lat, lon = parse_ssm_weather_file(file_wrapper)
        
        # Verify coordinates extraction
        self.assertEqual(lat, 48.283)
        self.assertEqual(lon, 16.467)
        
        # Verify columns renaming
        expected_cols = ['YEAR', 'DOY', 'TMAX', 'TMIN', 'SRAD', 'RAIN']
        self.assertEqual(list(df.columns), expected_cols)
        
        # Verify data values
        self.assertEqual(df.loc[0, 'YEAR'], 2025)
        self.assertEqual(df.loc[0, 'DOY'], 1)
        self.assertEqual(df.loc[0, 'TMAX'], 15.0)
        self.assertEqual(df.loc[0, 'TMIN'], 5.0)
        self.assertEqual(df.loc[0, 'SRAD'], 12.0)
        self.assertEqual(df.loc[0, 'RAIN'], 0.0)

    def test_biophysical_bounds_and_bad_data_interpolation(self):
        """
        Verify temperature and radiation outlier values are successfully marked as NaN
        and linearly interpolated using surrounding days instead of causing a crash.
        """
        # Create a 15-day CSV mock to keep the 95th percentile of SRAD < 40.0
        # Day 2 contains outliers (TMAX=99.0 C, TMIN=-50.0 C, SRAD=46.0 MJ)
        # Day 4 contains unparseable text ("corrupted", "invalid")
        csv_rows = [
            "LAT: 32.67 LON: 51.87",
            "YEAR,DOY,TMAX,TMIN,SRAD,RAIN",
            "2025,1,10.0,2.0,10.0,0.0",
            "2025,2,99.0,-50.0,46.0,1.0", # Outliers here
            "2025,3,12.0,4.0,12.0,2.0",
            "2025,4,corrupted,5.0,invalid,3.0", # Unparseable here
            "2025,5,14.0,6.0,14.0,4.0"
        ]
        
        # Add 10 normal days to keep the 95th percentile low
        for doy in range(6, 16):
            csv_rows.append(f"2025,{doy},15.0,7.0,15.0,0.0")
            
        csv_data = "\n".join(csv_rows)
        file_wrapper = io.BytesIO(csv_data.encode('utf-8'))
        file_wrapper.name = "mock_weather.csv"
        
        df, lat, lon = parse_ssm_weather_file(file_wrapper)
        
        self.assertEqual(len(df), 15)
        
        # Day 2 (index 1):
        # TMAX (99.0 C) is out of [-15, 60] -> NaN -> Interpolated between Day 1 (10.0) and Day 3 (12.0) -> 11.0
        self.assertEqual(df.loc[1, 'TMAX'], 11.0)
        # TMIN (-50.0 C) is out of [-15, 60] -> NaN -> Interpolated between Day 1 (2.0) and Day 3 (4.0) -> 3.0
        self.assertEqual(df.loc[1, 'TMIN'], 3.0)
        # SRAD (46.0 MJ) is out of [0, 45] -> NaN -> Interpolated between Day 1 (10.0) and Day 3 (12.0) -> 11.0
        self.assertEqual(df.loc[1, 'SRAD'], 11.0)
        
        # Day 4 (index 3):
        # TMAX ("corrupted") is unparseable -> NaN -> Interpolated between Day 3 (12.0) and Day 5 (14.0) -> 13.0
        self.assertEqual(df.loc[3, 'TMAX'], 13.0)
        # SRAD ("invalid") is unparseable -> NaN -> Interpolated between Day 3 (12.0) and Day 5 (14.0) -> 13.0
        self.assertEqual(df.loc[3, 'SRAD'], 13.0)

if __name__ == "__main__":
    unittest.main()
