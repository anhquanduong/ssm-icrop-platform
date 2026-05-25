import unittest
import pandas as pd
from app.core.model_engine import SSMiCropEngine
from app.core.weather_api import get_fallback_weather

class TestDualMode(unittest.TestCase):
    """
    Test suite verifying dual-mode execution (Classic vs Advanced) inside SSMiCropEngine.
    """

    def setUp(self):
        # Obtain standard weather series
        self.weather_df = get_fallback_weather('2020-05-01', '2020-09-30')
        self.soil_config = {
            'depth_mm': 1000.0, 
            'initial_water_percent': 10.0,  # Seed dry soil to induce stress
            'pawc_mm_m': 100.0
        }
        self.fertilizer_schedule = [{'doy': 130, 'nitrogen_kg_ha': 5.0}]  # Low nitrogen to induce stress

    def test_classic_mode_bypasses_stresses(self):
        """
        Asserts that under Classic execution:
        1. F_WATER and F_NUTR are locked exactly at 1.0.
        2. Soil outputs (SOIL_WATER, SOIL_N) remain locked at initial values.
        3. Model_Fidelity column correctly tracks the "Classic" execution mode.
        """
        engine_classic = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=self.fertilizer_schedule,
            mode="Classic"
        )
        
        results_df = engine_classic.run_simulation("Maize")
        
        # Verify Model_Fidelity tracks Classic
        self.assertIn("Model_Fidelity", results_df.columns)
        self.assertEqual(results_df["Model_Fidelity"].iloc[0], "Classic")
        self.assertTrue((results_df["Model_Fidelity"] == "Classic").all())
        
        # Assert stresses remain exactly 1.0
        self.assertTrue((results_df["F_WATER"] == 1.0).all())
        self.assertTrue((results_df["F_NUTR"] == 1.0).all())
        
        # Assert soil trackers remain locked
        initial_water = 1000.0 * (10.0 / 100.0)  # depth * pct / 100 = 100.0
        self.assertTrue((results_df["SOIL_WATER"] == round(initial_water, 2)).all())
        self.assertTrue((results_df["SOIL_N"] == 30.0).all())

    def test_advanced_mode_evaluates_stresses(self):
        """
        Asserts that under Advanced execution:
        1. F_WATER and/or F_NUTR drop below 1.0 under stressful dry soil/low N conditions.
        2. Soil trackers dynamically update rather than remaining locked.
        3. Model_Fidelity column tracks "Advanced".
        """
        engine_advanced = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=self.fertilizer_schedule,
            mode="Advanced"
        )
        
        results_df = engine_advanced.run_simulation("Maize")
        
        # Verify Model_Fidelity tracks Advanced
        self.assertIn("Model_Fidelity", results_df.columns)
        self.assertEqual(results_df["Model_Fidelity"].iloc[0], "Advanced")
        
        # Assert soil trackers are dynamic (they shouldn't remain constant)
        initial_water = 1000.0 * (10.0 / 100.0)
        self.assertFalse((results_df["SOIL_WATER"] == round(initial_water, 2)).all())
        
        # Check that stresses actually triggered (dropped below 1.0)
        self.assertTrue((results_df["F_WATER"] < 1.0).any() or (results_df["F_NUTR"] < 1.0).any())

    def test_outputs_are_structurally_identical(self):
        """
        Asserts that both modes yield structurally identical dataframes to support downstream visualization tools.
        """
        engine_classic = SSMiCropEngine(weather_df=self.weather_df, latitude=21.0285, mode="Classic")
        engine_advanced = SSMiCropEngine(weather_df=self.weather_df, latitude=21.0285, mode="Advanced")
        
        df_classic = engine_classic.run_simulation("Maize")
        df_advanced = engine_advanced.run_simulation("Maize")
        
        self.assertListEqual(list(df_classic.columns), list(df_advanced.columns))
        self.assertEqual(len(df_classic), len(df_advanced))

if __name__ == "__main__":
    unittest.main()
