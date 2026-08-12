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

    def test_capped_area_rows_are_included_in_equipment_totals(self):
        results = pd.DataFrame([
            {
                "Area_Coverage_sqft": 55_000,
                "Planning_Area_sqft": 18_000,
                "Number_of_required_DOTs_Radios": 4,
                "Result_Valid_For_Planning": True,
                "Is_Limiting_Band": True,
                "Coverage_Capped_To_Model_Range": False,
            },
            {
                "Area_Coverage_sqft": 45_000,
                "Planning_Area_sqft": 20_000,
                "Number_of_required_DOTs_Radios": 3,
                "Result_Valid_For_Planning": True,
                "Is_Limiting_Band": True,
                "Coverage_Capped_To_Model_Range": True,
            },
        ])

        summary = summarize_building_equipment(results)

        self.assertEqual(summary["Total_Coverage_Area_sqft"], 100_000)
        self.assertEqual(summary["Total_Required_DOTs_Radios"], 7)
        self.assertEqual(summary["Total_IRUs"], 1)

    def test_conversion_ratios_must_be_positive(self):
        results = pd.DataFrame(columns=[
            "Area_Coverage_sqft",
            "Planning_Area_sqft",
            "Number_of_required_DOTs_Radios",
        ])

        with self.assertRaises(ValueError):
            summarize_building_equipment(results, dots_per_iru=0)

    def test_capacity_focused_ratio_supports_5_point_5_dots_per_iru(self):
        results = pd.DataFrame([{
            "Area_Coverage_sqft": 120_000,
            "Planning_Area_sqft": 10_000,
            "Number_of_required_DOTs_Radios": 12,
            "Result_Valid_For_Planning": True,
            "Is_Limiting_Band": True,
        }])

        summary = summarize_building_equipment(results, dots_per_iru=5.5)

        self.assertEqual(summary["Total_IRUs"], 3)
        self.assertEqual(summary["DOTs_per_IRU"], 5.5)

if __name__ == "__main__":
    unittest.main()
