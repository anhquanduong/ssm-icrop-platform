import unittest
import pandas as pd
import numpy as np
import os
import sqlite3
from app.core.model_engine import SSMiCropEngine, DEFAULT_CROP_PARAMETERS
from app.core.weather_api import get_fallback_weather
from app.core.database import migrate_database_schema
from app.utils.db_manager import DatabaseManager

class TestPerennialEngine(unittest.TestCase):
    """
    Integration tests for Multi-Year Perennial Simulation Engine and Database Migrations.
    """

    def setUp(self):
        # Generate weather: standard 365-day weather series (DOY 1 to 365)
        # We can construct a simple DataFrame representing a year of weather
        dates = pd.date_range("2021-01-01", "2021-12-31")
        self.weather_df = pd.DataFrame({
            "DOY": [d.timetuple().tm_yday for d in dates],
            "SRAD": [15.0] * 365,
            "TMAX": [25.0] * 365,
            "TMIN": [15.0] * 365,
            "RAIN": [1.0] * 365,
            "TMP": [20.0] * 365
        })
        self.soil_config = {
            'depth_mm': 1200.0,
            'initial_water_percent': 50.0,
            'pawc_mm_m': 150.0
        }

    def test_database_migration(self):
        """
        Verify SQLite schema migration appends new columns and applies default backfills.
        """
        db_path = "test_temp_migration.db"
        if os.path.exists(db_path):
            os.remove(db_path)
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create an obsolete version of crop_profiles
        cursor.execute("""
            CREATE TABLE crop_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                crop_name TEXT NOT NULL,
                is_public INTEGER NOT NULL,
                parameters_json TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            INSERT INTO crop_profiles (user_id, crop_name, is_public, parameters_json)
            VALUES (1, 'Old Maize Profile', 1, '{}')
        """)
        conn.commit()
        
        # Execute migration
        migrate_database_schema(conn)
        
        # Verify schema is upgraded
        cursor.execute("PRAGMA table_info(crop_profiles)")
        cols = {col[1] for col in cursor.fetchall()}
        self.assertIn("crop_produce_type", cols)
        self.assertIn("lifecycle_strategy", cols)
        self.assertIn("t_dormancy_trigger", cols)
        self.assertIn("t_base_winter", cols)
        
        # Verify defaults are backfilled
        cursor.execute("SELECT crop_produce_type, lifecycle_strategy, t_dormancy_trigger, t_base_winter FROM crop_profiles")
        row = cursor.fetchone()
        self.assertEqual(row[0], "Fruit/Seed")
        self.assertEqual(row[1], "Annual (Single-Season)")
        self.assertEqual(row[2], 5.0)
        self.assertEqual(row[3], 0.0)
        
        conn.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_annual_multi_year_simulation(self):
        """
        Verify that an Annual crop simulated for 3 years resets AGB parameters yearly
        and allows full soil hydrology and nitrogen carry-overs continuously.
        """
        # Set up a Maize parameters set specifically
        DEFAULT_CROP_PARAMETERS["Maize"].update({
            "lifecycle_strategy": "Annual (Single-Season)",
            "t_dormancy_trigger": 5.0,
            "t_base_winter": 0.0
        })
        
        engine = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            sim_years=3
        )
        
        results_df = engine.run_simulation("Maize")
        
        # Should simulate for exactly 3 * 365 = 1095 days
        self.assertEqual(len(results_df), 1095)
        
        # Verify that years increment correctly
        self.assertListEqual(list(results_df["Current_Year"].unique()), [1, 2, 3])
        
        # Verify continuous timeline days calculation
        self.assertEqual(results_df["Simulation_Timeline_Days"].iloc[0], 1)
        self.assertEqual(results_df["Simulation_Timeline_Days"].iloc[-1], 3 * 365)
        
        # Check that leaf area index was reset at least twice
        # In Annual reset, at DOY 1 of Year 2 and Year 3, LAI is reset to 0.0
        y2_start = results_df[(results_df["Current_Year"] == 2) & (results_df["DOY"] == 1)].iloc[0]
        y3_start = results_df[(results_df["Current_Year"] == 3) & (results_df["DOY"] == 1)].iloc[0]
        self.assertEqual(y2_start["LAI"], 0.0)
        self.assertEqual(y3_start["LAI"], 0.0)

    def test_multi_year_accumulation_simulation(self):
        """
        Verify that a Multi-Year Accumulation strategy lets structural / root variables
        accumulate continuously without calendar year resets.
        """
        # Modify Sorghum profile temporarily to act as a Tuber/Root Multi-Year Accumulation crop
        DEFAULT_CROP_PARAMETERS["Sorghum"].update({
            "lifecycle_strategy": "Multi-Year Accumulation",
            "crop_produce_type": "Tuber/Root",
            "t_dormancy_trigger": 5.0,
            "t_base_winter": 0.0
        })
        
        engine = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            sim_years=2
        )
        
        results_df = engine.run_simulation("Sorghum")
        
        self.assertEqual(len(results_df), 730)
        
        # Root biomass (WROOT) should grow continuously without drops at year boundaries
        wroot_y1_end = results_df[(results_df["Current_Year"] == 1) & (results_df["DOY"] == 365)].iloc[0]["WROOT"]
        wroot_y2_start = results_df[(results_df["Current_Year"] == 2) & (results_df["DOY"] == 1)].iloc[0]["WROOT"]
        
        # WROOT at start of Year 2 should carry over and be at least equal to Year 1 end
        self.assertGreaterEqual(wroot_y2_start, wroot_y1_end)

    def test_cyclical_perennial_simulation(self):
        """
        Verify that Cyclical Perennial strategy resets wgrn = 0.0 and hi = 0.0 at year end if matured,
        while carrying over accumulated wood wwood framework continuously.
        """
        DEFAULT_CROP_PARAMETERS["Maize"].update({
            "lifecycle_strategy": "Cyclical Perennial",
            "crop_produce_type": "Fruit/Seed",
            "t_dormancy_trigger": 5.0,
            "t_base_winter": 0.0
        })
        
        engine = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            sim_years=2
        )
        
        results_df = engine.run_simulation("Maize")
        
        # Verify that wwood exists and increments (non-zero)
        self.assertIn("WWOOD", results_df.columns)
        self.assertTrue((results_df["WWOOD"] >= 0.0).all())
        
        wwood_y1_end = results_df[(results_df["Current_Year"] == 1) & (results_df["DOY"] == 365)].iloc[0]["WWOOD"]
        wwood_y2_start = results_df[(results_df["Current_Year"] == 2) & (results_df["DOY"] == 1)].iloc[0]["WWOOD"]
        
        # Wood carries over intact
        self.assertGreaterEqual(wwood_y2_start, wwood_y1_end)
        
        # Harvestable grain pool reset at the start of Year 2 (since Year 1 matured, cbd > bd_mat)
        wgrn_y2_start = results_df[(results_df["Current_Year"] == 2) & (results_df["DOY"] == 1)].iloc[0]["WGRN"]
        self.assertEqual(wgrn_y2_start, 0.0)

    def test_winter_dormancy_and_spring_flush(self):
        """
        Verify that cold weather triggers dormancy (leaf drop decay), swaps base metabolic temperatures,
        and 5 consecutive days of warm spring temperatures triggers a spring flush.
        """
        # Create a cold weather series to force dormancy, then warm up to trigger spring flush
        # Days 1 to 50: warm (20 C)
        # Days 51 to 100: cold (2 C) -> avg_temp_5d drops below t_dormancy_trigger (5.0) -> triggers dormancy
        # Days 101 to 150: warm (15 C) -> tmp >= 5.0 for 5 consecutive days -> triggers spring flush
        t_dormancy_trigger = 5.0
        temperatures = [20.0] * 50 + [2.0] * 50 + [15.0] * 50
        
        dates = pd.date_range("2020-05-01", periods=150)
        special_weather = pd.DataFrame({
            "DOY": [d.timetuple().tm_yday for d in dates],
            "SRAD": [15.0] * 150,
            "TMAX": [t + 2.0 for t in temperatures],
            "TMIN": [t - 2.0 for t in temperatures],
            "RAIN": [0.0] * 150,
            "TMP": temperatures
        })
        
        DEFAULT_CROP_PARAMETERS["Maize"].update({
            "lifecycle_strategy": "Cyclical Perennial",
            "t_dormancy_trigger": t_dormancy_trigger,
            "t_base_winter": -2.0,
            "TBD": 8.0
        })
        
        engine = SSMiCropEngine(
            weather_df=special_weather,
            latitude=21.0285,
            soil_config=self.soil_config,
            sim_years=1
        )
        
        results_df = engine.run_simulation("Maize")
        
        # Check that during cold period (days 51 to 100), LAI drops toward 0.05
        cold_lai_values = results_df["LAI"].iloc[50:100].values
        self.assertLessEqual(cold_lai_values[-1], 0.1) # Decayed leaf area
        
        # Check that after warming up (days 101 to 150), spring flush is triggered (LAI jumps to at least 0.5)
        warm_lai_values = results_df["LAI"].iloc[100:150].values
        self.assertGreaterEqual(warm_lai_values[-1], 0.5) # Re-awakened canopy

if __name__ == "__main__":
    unittest.main()
