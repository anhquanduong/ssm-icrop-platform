import unittest
import pandas as pd
from app.core.model_engine import SSMiCropEngine, SimulationResultDataFrame
from app.core.weather_api import get_fallback_weather

class TestDiagnosticLogger(unittest.TestCase):
    """
    Unit test suite verifying the behavior of the Live Diagnostic Array Logger integration.
    """

    def setUp(self):
        # Obtain standard weather series
        self.weather_df = get_fallback_weather('2020-05-01', '2020-09-30')
        self.soil_config = {
            'depth_mm': 1000.0, 
            'initial_water_percent': 50.0,
            'pawc_mm_m': 150.0
        }
        self.fertilizer_schedule = [{'doy': 130, 'nitrogen_kg_ha': 50.0}]

    def test_run_simulation_returns_subclass(self):
        """
        Asserts that SSMiCropEngine.run_simulation returns a SimulationResultDataFrame
        which is a subclass of pd.DataFrame and has the custom diagnostic_df key.
        """
        engine = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=self.fertilizer_schedule,
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": True,
                "use_root_growth": True,
                "use_heat_shock": True
            }
        )
        
        results_df = engine.run_simulation("Maize")
        
        # Verify type constraints
        self.assertIsInstance(results_df, pd.DataFrame)
        self.assertIsInstance(results_df, SimulationResultDataFrame)
        
        # Check standard columns are intact
        self.assertIn("LAI", results_df.columns)
        self.assertIn("WTOP", results_df.columns)
        
        # Retrieve diagnostic dataframe
        diag_df = results_df["diagnostic_df"]
        self.assertIsInstance(diag_df, pd.DataFrame)
        
        # Verify internal daily tracking keys are present and mapped
        expected_keys = ["DAP", "DRAIN", "SNAVL", "NLEACH", "NST"]
        for key in expected_keys:
            self.assertIn(key, diag_df.columns)
            
        # Assert diagnostic matrix is not empty and matches row length
        self.assertEqual(len(diag_df), len(results_df))
        
        # Check that DAP increments sequentially
        self.assertEqual(list(diag_df["DAP"]), list(results_df["DAP"]))

if __name__ == "__main__":
    unittest.main()
