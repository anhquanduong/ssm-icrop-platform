import unittest
from unittest.mock import patch, MagicMock
import requests

from app.core.soil_api import fetch_isric_soil_data

class TestSoilGridsAPI(unittest.TestCase):
    """
    Test suite for fetch_isric_soil_data from soil_api.py.
    """

    @patch("requests.Session.get")
    def test_fetch_success_calculation(self, mock_get):
        """
        Verify correct pedotransfer conversion of SoilGrids JSON payload under optimal success.
        """
        # Mock successful JSON response matching the actual SoilGrids v2.0 structure
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {
                "layers": [
                    {
                        "name": "clay",
                        "depths": [
                            {"label": "0-5cm", "values": {"mean": 280}},     # 28%
                            {"label": "5-15cm", "values": {"mean": 290}},    # 29%
                            {"label": "15-30cm", "values": {"mean": 300}},   # 30%
                            {"label": "60-100cm", "values": {"mean": 350}}   # Should be ignored (out of 0-30cm range)
                        ]
                    },
                    {
                        "name": "sand",
                        "depths": [
                            {"label": "0-5cm", "values": {"mean": 320}},     # 32%
                            {"label": "5-15cm", "values": {"mean": 330}},    # 33%
                            {"label": "15-30cm", "values": {"mean": 340}}    # 34%
                        ]
                    },
                    {
                        "name": "soc",
                        "depths": [
                            {"label": "0-5cm", "values": {"mean": 240}},     # dg/kg
                            {"label": "5-15cm", "values": {"mean": 250}},    # dg/kg
                            {"label": "15-30cm", "values": {"mean": 260}}    # dg/kg
                        ]
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        # Target Coordinates (Vienna-Gerasdorf study region)
        result = fetch_isric_soil_data(48.2830, 16.4670)

        # Expected calculations checking:
        # Clay mean across 0-30cm = (280 + 290 + 300) / 3 = 290 g/kg -> 29.0 %
        # Sand mean across 0-30cm = (320 + 330 + 340) / 3 = 330 g/kg -> 33.0 %
        # SOC mean across 0-30cm = (240 + 250 + 260) / 3 = 250 dg/kg
        #
        # SOM = (250 / 100.0) * 1.724 = 2.5 * 1.724 = 4.31 % (rounded to 4.31)
        # PAWC = 200.0 - (1.5 * 33.0) + (0.5 * 29.0) = 200.0 - 49.5 + 14.5 = 165.0 mm/m (rounded to 165.0)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["som"], 4.31)
        self.assertEqual(result["pawc"], 165.0)
        self.assertEqual(result["root_zone_depth"], 1000)

    @patch("requests.Session.get")
    def test_fetch_timeout_fallback(self, mock_get):
        """
        Verify that a network timeout raises an exception and returns stable fallbacks.
        """
        # Simulate network timeout exception
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out after 3.0 seconds")

        result = fetch_isric_soil_data(21.0285, 105.8542)

        # Assert correct default baseline values are assigned gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result["som"], 2.1)
        self.assertEqual(result["pawc"], 140.0)
        self.assertEqual(result["root_zone_depth"], 1000)
        self.assertTrue(result.get("is_fallback"))

    @patch("requests.Session.get")
    def test_fetch_ocean_status_fallback(self, mock_get):
        """
        Verify that querying an ocean pixel returns fallback values.
        """
        # Mock 400 Bad Request / Out of Bounds response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_get.return_value = mock_response

        # Coordinate in the Atlantic Ocean
        result = fetch_isric_soil_data(25.0, -45.0)

        self.assertIsNotNone(result)
        self.assertEqual(result["som"], 2.1)
        self.assertEqual(result["pawc"], 140.0)
        self.assertEqual(result["root_zone_depth"], 1000)
        self.assertTrue(result.get("is_fallback"))

    def test_coordinates_out_of_bounds_fallback(self):
        """
        Verify that passing extreme coordinates instantly triggers fallbacks without fetching.
        """
        result = fetch_isric_soil_data(95.0, 200.0)

        self.assertIsNotNone(result)
        self.assertEqual(result["som"], 2.1)
        self.assertEqual(result["pawc"], 140.0)
        self.assertEqual(result["root_zone_depth"], 1000)
        self.assertTrue(result.get("is_fallback"))

if __name__ == "__main__":
    unittest.main()
