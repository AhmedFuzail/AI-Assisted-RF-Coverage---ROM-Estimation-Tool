import unittest

import pandas as pd

from coverage_engine import summarize_building_equipment


class BuildingEquipmentSummaryTests(unittest.TestCase):
    def test_66_radios_rounds_up_to_10_irus_and_1_bbu(self):
        results = pd.DataFrame([
            {
                "Area_Coverage_sqft": 660_000,
                "Planning_Area_sqft": 10_000,
                "Number_of_required_DOTs_Radios": 66,
                "Result_Valid_For_Planning": True,
                "Is_Limiting_Band": True,
            }
        ])

        summary = summarize_building_equipment(results)

        self.assertEqual(summary["Average_sqft_per_DOT_Radio"], 10_000)
        self.assertEqual(summary["Total_Required_DOTs_Radios"], 66)
        self.assertEqual(summary["Total_IRUs"], 10)
        self.assertEqual(summary["Total_BBUs"], 1)

    def test_average_uses_all_valid_area_allocations(self):
        results = pd.DataFrame([
            {
                "Area_Coverage_sqft": 30_000,
                "Planning_Area_sqft": 11_000,
                "Number_of_required_DOTs_Radios": 3,
                "Result_Valid_For_Planning": True,
                "Is_Limiting_Band": True,
            },
            {
                "Area_Coverage_sqft": 100_000,
                "Planning_Area_sqft": 15_000,
                "Number_of_required_DOTs_Radios": 7,
                "Result_Valid_For_Planning": True,
                "Is_Limiting_Band": True,
            },
        ])

        summary = summarize_building_equipment(results)

        self.assertEqual(summary["Total_Coverage_Area_sqft"], 130_000)
        self.assertEqual(summary["Average_sqft_per_DOT_Radio"], 13_000)
        self.assertEqual(summary["Total_Required_DOTs_Radios"], 10)
        self.assertEqual(summary["Total_IRUs"], 2)
        self.assertEqual(summary["Total_BBUs"], 1)

    def test_nonlimiting_and_invalid_rows_are_excluded(self):
        results = pd.DataFrame([
            {
                "Area_Coverage_sqft": 20_000,
                "Planning_Area_sqft": 20_000,
                "Number_of_required_DOTs_Radios": 1,
                "Result_Valid_For_Planning": True,
                "Is_Limiting_Band": True,
            },
            {
                "Area_Coverage_sqft": 20_000,
                "Planning_Area_sqft": 10_000,
                "Number_of_required_DOTs_Radios": 2,
                "Result_Valid_For_Planning": True,
                "Is_Limiting_Band": False,
            },
            {
                "Area_Coverage_sqft": 50_000,
                "Planning_Area_sqft": 10_000,
                "Number_of_required_DOTs_Radios": 5,
                "Result_Valid_For_Planning": False,
                "Is_Limiting_Band": True,
            },
        ])

        summary = summarize_building_equipment(results)

        self.assertEqual(summary["Total_Coverage_Area_sqft"], 20_000)
        self.assertEqual(summary["Total_Required_DOTs_Radios"], 1)
        self.assertEqual(summary["Total_IRUs"], 1)
        self.assertEqual(summary["Total_BBUs"], 1)

    def test_conversion_ratios_must_be_positive(self):
        results = pd.DataFrame(columns=[
            "Area_Coverage_sqft",
            "Planning_Area_sqft",
            "Number_of_required_DOTs_Radios",
        ])

        with self.assertRaises(ValueError):
            summarize_building_equipment(results, dots_per_iru=0)


if __name__ == "__main__":
    unittest.main()