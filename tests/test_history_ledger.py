import unittest
import pandas as pd
from app.utils.history_ledger import format_simulation_run

class TestHistoryLedger(unittest.TestCase):
    """
    Test suite for the history logging and dataframe preparation module history_ledger.py.
    """

    def test_format_success(self):
        """
        Verify that a correct simulation dataframe is cleaned and converted.
        """
        raw_df = pd.DataFrame({
            "DOY": [120, 121, 122],
            "WTOP": [15.0, 30.5, 50.0],  # g/m²
            "LAI": [0.2, 0.45, 0.85],
            "TMP": [22.0, 23.5, 21.0]   # Extra column to discard
        })
        
        scenario_name = "Dynamic Scenario A"
        formatted_df = format_simulation_run(raw_df, scenario_name)
        
        self.assertEqual(list(formatted_df.columns), ["DOY", "BIOMASS", "LAI", "F_WATER", "F_NUTR", "Model_Fidelity", "Management", "Scenario"])
        
        # Verify default stress index values are set when missing from results_df
        self.assertListEqual(list(formatted_df["F_WATER"].values), [1.0] * 3)
        self.assertListEqual(list(formatted_df["F_NUTR"].values), [1.0] * 3)
        
        # Verify units conversion: 1 g/m² = 10 kg/ha
        # 15.0 g/m² * 10 = 150.0 kg/ha
        # 30.5 g/m² * 10 = 305.0 kg/ha
        # 50.0 g/m² * 10 = 500.0 kg/ha
        self.assertListEqual(list(formatted_df["BIOMASS"].values), [150.0, 305.0, 500.0])
        self.assertListEqual(list(formatted_df["DOY"].values), [120, 121, 122])
        self.assertListEqual(list(formatted_df["LAI"].values), [0.2, 0.45, 0.85])
        self.assertListEqual(list(formatted_df["Scenario"].values), [scenario_name] * 3)

    def test_missing_column_error(self):
        """
        Verify that a KeyError is thrown if any mandatory simulation output variable is missing.
        """
        # Missing 'WTOP' column
        bad_df = pd.DataFrame({
            "DOY": [120, 121],
            "LAI": [0.2, 0.4]
        })
        
        with self.assertRaises(KeyError):
            format_simulation_run(bad_df, "Failure Scenario")

    def test_multiple_runs_concatenation(self):
        """
        Verify that multiple compiled scenarios concatenate cleanly using pd.concat.
        """
        run1 = pd.DataFrame({"DOY": [10, 20], "WTOP": [1.0, 2.0], "LAI": [0.1, 0.2]})
        run2 = pd.DataFrame({"DOY": [10, 20], "WTOP": [1.5, 2.5], "LAI": [0.15, 0.25]})
        
        f1 = format_simulation_run(run1, "Run1")
        f2 = format_simulation_run(run2, "Run2")
        
        combined = pd.concat([f1, f2], ignore_index=True)
        self.assertEqual(len(combined), 4)
        self.assertListEqual(list(combined["Scenario"].values), ["Run1", "Run1", "Run2", "Run2"])

if __name__ == "__main__":
    unittest.main()
