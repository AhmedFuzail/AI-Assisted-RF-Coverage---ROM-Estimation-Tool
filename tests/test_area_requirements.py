import math
import unittest

import pandas as pd

from coverage_engine import calculate_building_coverage, calculate_coverage_for_all_buildings


def area_record(**updates):
    record = {
        "Building_ID": "legacy-building-1",
        "Building_Name": "Test Venue",
        "Building_Type": "Industrial",
        "Category": "Warehouse",
        "Sub_Type_A": "Warehouse / Storage Area",
        "Coverage Area": 50_000,
        "Concrete_%": 25,
        "Drywall_%": 10,
        "Glass_%": 0,
        "Metal_%": 65,
        "Open_Area_%": 10,
        "Light_Clutter_%": 20,
        "Medium_Clutter_%": 30,
        "Dense_Clutter_%": 40,
        "Ceiling_Height_Class": "Low_8_12ft",
        "Environment_Type": "Indoor_Industrial",
        "Layout_Complexity": "Complex",
        "Mobility_Pattern": "Static",
        "Assumption_Profile": "Warehouse",
    }
    record.update(updates)
    return record


def nr_mapl():
    return {
        "Technology": "NR",
        "Band": "B48",
        "Frequency_MHz": 3625,
        "Bandwidth_MHz": 40,
        "SCS_kHz": 30,
        "RB_Count": 106,
        "MAPL_Before_Margin_dB": 95.25512888687605,
    }


class AreaRequirementTests(unittest.TestCase):
    def test_legacy_building_id_is_exposed_as_area_id(self):
        result = calculate_building_coverage(area_record(), nr_mapl(), margin_db=6)
        self.assertEqual(result["Area_ID"], "legacy-building-1")
        self.assertNotIn("Building_ID", result)
        self.assertEqual(result["Area_Coverage_sqft"], 50_000)

    def test_required_radios_rounds_up(self):
        baseline = calculate_building_coverage(area_record(), nr_mapl(), margin_db=6)
        per_radio_coverage = baseline["Planning_Area_sqft"]
        result = calculate_building_coverage(
            area_record(**{"Coverage Area": per_radio_coverage * 2.01}),
            nr_mapl(),
            margin_db=6,
        )
        self.assertEqual(result["Number_of_required_DOTs_Radios"], 3)
        self.assertEqual(
            result["Number_of_required_DOTs_Radios"],
            math.ceil(result["Area_Coverage_sqft"] / result["Planning_Area_sqft"]),
        )

    def test_zero_area_requires_zero_radios(self):
        result = calculate_building_coverage(area_record(**{"Coverage Area": 0}), nr_mapl(), margin_db=6)
        self.assertEqual(result["Number_of_required_DOTs_Radios"], 0)

    def test_missing_area_returns_warning_instead_of_crashing(self):
        record = area_record()
        record.pop("Coverage Area")
        result = calculate_building_coverage(record, nr_mapl(), margin_db=6)
        self.assertIsNone(result["Number_of_required_DOTs_Radios"])
        self.assertIn("Area coverage is missing", result["Warnings"])

    def test_batch_assigns_area_id_and_uses_it_for_overrides(self):
        record = area_record()
        record.pop("Building_ID")
        results = calculate_coverage_for_all_buildings(
            pd.DataFrame([record]),
            [nr_mapl()],
            margin_db=6,
            overrides={"area-1": {"area_efficiency": 0.30}},
        )
        self.assertEqual(results.iloc[0]["Area_ID"], "area-1")
        self.assertEqual(results.iloc[0]["Area_Efficiency"], 0.30)
        self.assertIn("Area_Efficiency", results.iloc[0]["Override_Fields"])


if __name__ == "__main__":
    unittest.main()
