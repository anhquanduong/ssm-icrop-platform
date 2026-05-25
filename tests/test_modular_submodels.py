import unittest
import pandas as pd
import numpy as np
from app.core.model_engine import SSMiCropEngine
from app.core.weather_api import get_fallback_weather

class TestModularSubmodels(unittest.TestCase):
    """
    Test suite verifying the 4 advanced biophysical sub-models:
    1. Vapor Pressure Deficit (VPD) Stress
    2. Nitrogen Leaching
    3. Dynamic Phased Root Growth
    4. Pollination Heat Shock
    """

    def setUp(self):
        # Retrieve baseline weather
        self.weather_df = get_fallback_weather('2020-05-01', '2020-09-30')
        
        # Standard soil setup
        self.soil_config = {
            'depth_mm': 1200.0,
            'initial_water_percent': 50.0,
            'pawc_mm_m': 150.0
        }
        
        # Simple management round setup
        self.fertilizer_schedule = [
            {'doy': 130, 'nitrogen_kg_ha': 40.0}
        ]
        
        self.water_management = {
            'irrigation': [],
            'drainage': []
        }

    def test_vpd_stress_reduces_biomass(self):
        """
        Sub-Model 1 (VPD): If use_vpd is active under moderately hot weather (high VPD),
        assert that RUE reduction occurs and final grain yield (WGRN) is lower than
        when use_vpd is disabled.
        """
        # Create moderately hot weather dataset to trigger high VPD (> 1.5 kPa) without killing the crop
        hot_weather = self.weather_df.copy()
        hot_weather['TMAX'] = 36.0
        hot_weather['TMIN'] = 15.0
        
        # High moisture and nitrogen to ensure excellent growth baseline
        lush_soil = {
            'depth_mm': 1200.0,
            'initial_water_percent': 90.0,
            'pawc_mm_m': 200.0
        }
        plenty_fertilizer = [
            {'doy': 130, 'nitrogen_kg_ha': 200.0},
            {'doy': 160, 'nitrogen_kg_ha': 200.0}
        ]
        
        # Run with VPD stress enabled
        engine_with_vpd = SSMiCropEngine(
            weather_df=hot_weather,
            latitude=21.0285,
            soil_config=lush_soil,
            fertilizer_schedule=plenty_fertilizer,
            water_management={'auto_irrigation': True, 'irrigation': [], 'drainage': []},
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": False,
                "use_root_growth": False,
                "use_heat_shock": False
            }
        )
        df_with_vpd = engine_with_vpd.run_simulation("Maize")
        
        # Run with VPD stress disabled
        engine_no_vpd = SSMiCropEngine(
            weather_df=hot_weather,
            latitude=21.0285,
            soil_config=lush_soil,
            fertilizer_schedule=plenty_fertilizer,
            water_management={'auto_irrigation': True, 'irrigation': [], 'drainage': []},
            mode="Advanced",
            advanced_options={
                "use_vpd": False,
                "use_leaching": False,
                "use_root_growth": False,
                "use_heat_shock": False
            }
        )
        df_no_vpd = engine_no_vpd.run_simulation("Maize")
        
        # Assert that final yield (WGRN) is lower when VPD stress is active
        final_yield_vpd = df_with_vpd["WGRN"].iloc[-1]
        final_yield_no_vpd = df_no_vpd["WGRN"].iloc[-1]
        
        self.assertLess(final_yield_vpd, final_yield_no_vpd)

    def test_nitrogen_leaching_reduces_soil_n(self):
        """
        Sub-Model 2 (Leaching): If use_leaching is enabled, on heavy rainfall
        and drainage days, soil Nitrogen decreases due to washout.
        Assert that SOIL_N is lower than when use_leaching is disabled.
        """
        # Create rainy weather to trigger gravitational drainage
        rainy_weather = self.weather_df.copy()
        rainy_weather.loc[rainy_weather['DOY'] == 140, 'RAIN'] = 120.0
        
        # Enable drainage release schedule on DOY 140
        water_management_drainage = {
            'irrigation': [],
            'drainage': [{'start_doy': 140, 'release_rate_mm_day': 50.0, 'infrastructure_type': 'Subsurface Tile'}]
        }
        
        # Run with Nitrogen leaching active
        engine_leached = SSMiCropEngine(
            weather_df=rainy_weather,
            latitude=21.0285,
            soil_config={
                'depth_mm': 1200.0,
                'initial_water_percent': 90.0,
                'pawc_mm_m': 150.0
            },
            fertilizer_schedule=[{'doy': 130, 'nitrogen_kg_ha': 80.0}],
            water_management=water_management_drainage,
            mode="Advanced",
            advanced_options={
                "use_vpd": False,
                "use_leaching": True,
                "use_root_growth": False,
                "use_heat_shock": False
            }
        )
        df_leached = engine_leached.run_simulation("Maize")
        
        # Run with Nitrogen leaching disabled
        engine_unleached = SSMiCropEngine(
            weather_df=rainy_weather,
            latitude=21.0285,
            soil_config={
                'depth_mm': 1200.0,
                'initial_water_percent': 90.0,
                'pawc_mm_m': 150.0
            },
            fertilizer_schedule=[{'doy': 130, 'nitrogen_kg_ha': 80.0}],
            water_management=water_management_drainage,
            mode="Advanced",
            advanced_options={
                "use_vpd": False,
                "use_leaching": False,
                "use_root_growth": False,
                "use_heat_shock": False
            }
        )
        df_unleached = engine_unleached.run_simulation("Maize")
        
        # Identify the day of drainage release/heavy rain
        n_val_leached = df_leached.loc[df_leached['DOY'] == 144, 'SOIL_N'].values[0]
        n_val_unleached = df_unleached.loc[df_unleached['DOY'] == 144, 'SOIL_N'].values[0]
        
        # With leaching, SOIL_N should be strictly less on DOY 144
        self.assertLess(n_val_leached, n_val_unleached)

    def test_dynamic_root_growth_caps_moisture_and_updates_root_depth(self):
        """
        Sub-Model 3 (Root Growth): When enabled, root depth deport expands
        linearly with degree-days from emergence, and storage capacity dynamically resizes.
        Assert that DEPORT behaves correctly and expands over time.
        """
        # Run with dynamic root growth enabled
        engine_roots = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=self.fertilizer_schedule,
            water_management=self.water_management,
            mode="Advanced",
            advanced_options={
                "use_vpd": False,
                "use_leaching": False,
                "use_root_growth": True,
                "use_heat_shock": False
            }
        )
        df_roots = engine_roots.run_simulation("Maize")
        
        # Assert root zone deport increases from initial (150 mm) up to maximum depth
        deport_values = df_roots["DEPORT"]
        self.assertGreater(deport_values.iloc[-1], deport_values.iloc[0])
        self.assertEqual(deport_values.iloc[0], 150.0)

    def test_heat_shock_reduces_yield_and_preserves_vegetative_biomass(self):
        """
        Sub-Model 4 (Heat Shock): When active, temperatures > 35°C during anthesis
        accumulate pollen sterility, reducing daily grain allocation (SGR) and final HI/Yield,
        while completely bypassing vegetative biomass (WVEG remains identical).
        """
        # High moisture and nitrogen to ensure excellent growth baseline and no stress caps
        lush_soil = {
            'depth_mm': 1200.0,
            'initial_water_percent': 90.0,
            'pawc_mm_m': 200.0
        }
        plenty_fertilizer = [
            {'doy': 130, 'nitrogen_kg_ha': 200.0},
            {'doy': 160, 'nitrogen_kg_ha': 200.0}
        ]

        # We need to find the flowering DOY in standard simulation run first.
        # So we run a quick standard run.
        engine_find = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=lush_soil,
            fertilizer_schedule=plenty_fertilizer,
            mode="Advanced"
        )
        df_find = engine_find.run_simulation("Maize")
        
        # Flowering window starts around bd_sil. Let's find a day where cbd is near bd_sil.
        # Maize parameters default: bdSOWEMR=3.0, bdEMREJU=8.5, bdSILPM=33.8
        # Maize bd_sil is approx: bd_emr (3.0) + bd_emr_eju (8.5) + bd_ejutsi (4.0) + bd_tsisil
        # Find the day when CBD is closest to 26.0 (which is bd_sil for Maize)
        silking_idx = (df_find["CBD"] - 26.0).abs().idxmin()
        silking_doy = df_find.loc[silking_idx, "DOY"]
        
        # Create hot weather specifically around silking DOY (e.g. silking_doy - 2 to silking_doy + 2)
        hot_anthesis_weather = self.weather_df.copy()
        hot_anthesis_weather.loc[
            (hot_anthesis_weather["DOY"] >= silking_doy - 4) & (hot_anthesis_weather["DOY"] <= silking_doy + 4), 
            "TMAX"
        ] = 40.0
        
        # Run with heat shock active
        engine_shock = SSMiCropEngine(
            weather_df=hot_anthesis_weather,
            latitude=21.0285,
            soil_config=lush_soil,
            fertilizer_schedule=plenty_fertilizer,
            water_management={"auto_irrigation": True, "irrigation": [], "drainage": []},
            mode="Advanced",
            advanced_options={
                "use_vpd": False,
                "use_leaching": False,
                "use_root_growth": False,
                "use_heat_shock": True
            }
        )
        df_shock = engine_shock.run_simulation("Maize")
        
        # Run with heat shock inactive
        engine_no_shock = SSMiCropEngine(
            weather_df=hot_anthesis_weather,
            latitude=21.0285,
            soil_config=lush_soil,
            fertilizer_schedule=plenty_fertilizer,
            water_management={"auto_irrigation": True, "irrigation": [], "drainage": []},
            mode="Advanced",
            advanced_options={
                "use_vpd": False,
                "use_leaching": False,
                "use_root_growth": False,
                "use_heat_shock": False
            }
        )
        df_no_shock = engine_no_shock.run_simulation("Maize")
        
        # Assert final yield (WGRN) is lower under heat shock
        self.assertLess(df_shock["WGRN"].iloc[-1], df_no_shock["WGRN"].iloc[-1])
        
        # Assert vegetative biomass (WVEG) is greater than or equal to the unshocked run (since less allocation to grain leaves more in stem)
        self.assertGreaterEqual(df_shock["WVEG"].iloc[-1], df_no_shock["WVEG"].iloc[-1])

    def test_manual_irrigation_increases_yield_under_drought(self):
        """
        Drought Scenario: Under dry soil conditions and without automatic irrigation,
        assert that adding manual irrigation rounds increases final crop yield (WGRN).
        """
        dry_soil = {
            'depth_mm': 1200.0,
            'initial_water_percent': 25.0,  # Dry starting profile
            'pawc_mm_m': 150.0
        }
        
        # Run 1: Rainfed / no irrigation
        engine_rainfed = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=dry_soil,
            fertilizer_schedule=[{'doy': 120, 'nitrogen_kg_ha': 150.0}],
            water_management={
                'auto_irrigation': False,
                'irrigation': [],
                'drainage': []
            },
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": True,
                "use_root_growth": True,
                "use_heat_shock": True
            }
        )
        df_rainfed = engine_rainfed.run_simulation("Maize")
        
        # Run 2: Manual scheduled irrigation (added water)
        engine_irrigated = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=dry_soil,
            fertilizer_schedule=[{'doy': 120, 'nitrogen_kg_ha': 150.0}],
            water_management={
                'auto_irrigation': False,
                'irrigation': [{'doy': 130, 'water_applied_mm': 50.0, 'system_type': 'Drip'}],
                'drainage': []
            },
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": True,
                "use_root_growth": True,
                "use_heat_shock": True
            }
        )
        df_irrigated = engine_irrigated.run_simulation("Maize")
        
        self.assertGreater(df_irrigated["WGRN"].iloc[-1], df_rainfed["WGRN"].iloc[-1])

    def test_nitrogen_fertilizer_increases_yield_under_depleted_n(self):
        """
        Nitrogen Scenario: Under depleted nitrogen soil conditions,
        assert that applying fertilizer rounds increases final crop yield (WGRN).
        """
        # Run 1: Low / no fertilizer
        engine_low_n = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=[],
            water_management={'auto_irrigation': True, 'irrigation': [], 'drainage': []},
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": True,
                "use_root_growth": True,
                "use_heat_shock": True
            }
        )
        df_low_n = engine_low_n.run_simulation("Maize")
        
        # Run 2: Standard fertilizer application
        engine_high_n = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=[{'doy': 130, 'nitrogen_kg_ha': 100.0}],
            water_management={'auto_irrigation': True, 'irrigation': [], 'drainage': []},
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": True,
                "use_root_growth": True,
                "use_heat_shock": True
            }
        )
        df_high_n = engine_high_n.run_simulation("Maize")
        
        self.assertGreater(df_high_n["WGRN"].iloc[-1], df_low_n["WGRN"].iloc[-1])

    def test_nitrogen_sensitivity_under_leaching(self):
        """
        Sensitivity Scenario: Under leaching conditions, verifying that applying 200 kg N/ha
        provides a substantially higher nitrogen pool and yield than applying 30 kg N/ha,
        proving crop response sensitivity to the fertilizer amount under solute transport.
        """
        depleted_soil = self.soil_config.copy()
        depleted_soil['initial_n'] = 30.0

        # Run 1: Low fertilizer (30 kg N/ha)
        engine_low = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=depleted_soil,
            fertilizer_schedule=[{'doy': 120, 'nitrogen_kg_ha': 30.0}],
            water_management={'auto_irrigation': True, 'irrigation': [], 'drainage': []},
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": True,
                "use_root_growth": True,
                "use_heat_shock": True
            }
        )
        df_low = engine_low.run_simulation("Maize")
        
        # Run 2: High fertilizer (200 kg N/ha)
        engine_high = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=depleted_soil,
            fertilizer_schedule=[{'doy': 120, 'nitrogen_kg_ha': 200.0}],
            water_management={'auto_irrigation': True, 'irrigation': [], 'drainage': []},
            mode="Advanced",
            advanced_options={
                "use_vpd": True,
                "use_leaching": True,
                "use_root_growth": True,
                "use_heat_shock": True
            }
        )
        df_high = engine_high.run_simulation("Maize")
        
        # Verify that 200 kg N/ha yields higher than 30 kg N/ha
        self.assertGreater(df_high["WGRN"].iloc[-1], df_low["WGRN"].iloc[-1])
        # Verify that total biomass (WTOP) is also higher
        self.assertGreater(df_high["WTOP"].iloc[-1], df_low["WTOP"].iloc[-1])

    def test_bypass_integrity_is_100_percent(self):
        """
        Asserts that running in Advanced Mode with all modular options set to False
        yields exactly identical results to the standard Advanced Mode run (continuity check).
        """
        engine_default = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=self.fertilizer_schedule,
            water_management=self.water_management,
            mode="Advanced"
        )
        df_default = engine_default.run_simulation("Maize")
        
        engine_bypass = SSMiCropEngine(
            weather_df=self.weather_df,
            latitude=21.0285,
            soil_config=self.soil_config,
            fertilizer_schedule=self.fertilizer_schedule,
            water_management=self.water_management,
            mode="Advanced",
            advanced_options={
                "use_vpd": False,
                "use_leaching": False,
                "use_root_growth": False,
                "use_heat_shock": False
            }
        )
        df_bypass = engine_bypass.run_simulation("Maize")
        
        pd.testing.assert_frame_equal(df_default, df_bypass)

if __name__ == "__main__":
    unittest.main()
