import math
import unittest

import pandas as pd

from coverage_engine import (
    BAND_CENTER_FREQUENCY_MHZ,
    STREAMLIT_DESIGN_MARGIN_DB,
    STREAMLIT_DESIGN_MARGIN_BY_OPERATOR_DB,
    RESULT_COLUMNS,
    calculate_area_efficiency,
    calculate_building_coverage,
    calculate_coverage_for_all_buildings,
    calculate_incremental_loss_db,
    classify_los_nlos,
    convert_mapl_to_coverage,
    map_building_to_itu_environment,
    resolve_frequency_mhz,
    resolve_radio_power_mw,
    resolve_streamlit_design_margin_db,
    resolve_technology,
)


def open_office(**updates):
    record = {
        "Building_ID": "building-1",
        "Building_Name": "Test Venue",
        "Building_Type": "Office",
        "Category": "Open_Office",
        "Sub_Type_A": "Open Work Area / Benching",
        "Coverage Area": 50_000,
        "Concrete_%": 10,
        "Drywall_%": 55,
        "Glass_%": 25,
        "Metal_%": 10,
        "Open_Area_%": 55,
        "Light_Clutter_%": 30,
        "Medium_Clutter_%": 12,
        "Dense_Clutter_%": 3,
        "Ceiling_Height_Class": "Medium_12_18ft",
        "Environment_Type": "Indoor_Conditioned",
        "Layout_Complexity": "Moderate",
        "Mobility_Pattern": "Low_Mobility",
        "Total Losses Material": 6.0,
        "Total Loss Density": 2.5,
        "Total Loss": 8.5,
        "Assumption_Profile": "Office_Open",
    }
    record.update(updates)
    return record


def dense_industrial(**updates):
    record = {
        "Building_ID": "building-2",
        "Building_Name": "Industrial Test",
        "Building_Type": "Industrial",
        "Category": "Warehouse",
        "Sub_Type_A": "Support / Storage / IT",
        "Coverage Area": 40_000,
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
        "Total Losses Material": 15.1,
        "Total Loss Density": 6.5,
        "Total Loss": 21.6,
        "Assumption_Profile": "IT_MEP",
    }
    record.update(updates)
    return record


def mapl(technology="LTE", band="B2/B25", frequency_mhz=None, bandwidth_mhz=20, scs_khz=15, rb_count=100, mapl_db=90.2287874528):
    return {
        "Technology": technology,
        "Band": band,
        "Frequency_MHz": frequency_mhz,
        "Bandwidth_MHz": bandwidth_mhz,
        "SCS_kHz": scs_khz,
        "RB_Count": rb_count,
        "MAPL_Before_Margin_dB": mapl_db,
    }


class CoverageEngineTests(unittest.TestCase):

    def test_streamlit_design_margin_policy_is_calibrated_by_design_type(self):
        self.assertEqual(STREAMLIT_DESIGN_MARGIN_DB, 14.0)
        self.assertEqual(
            STREAMLIT_DESIGN_MARGIN_BY_OPERATOR_DB["Enterprise Private 5G"],
            15.5,
        )
        self.assertEqual(
            STREAMLIT_DESIGN_MARGIN_BY_OPERATOR_DB["Enterprise 5G Coverage"],
            24.85,
        )
        self.assertEqual(
            resolve_streamlit_design_margin_db("Enterprise Private 5G"),
            15.5,
        )
        self.assertEqual(
            resolve_streamlit_design_margin_db(" Enterprise 5G Coverage "),
            24.85,
        )
        self.assertEqual(resolve_streamlit_design_margin_db(""), 14.0)

    def test_lte_20_mhz_at_1900_mhz(self):
        result = convert_mapl_to_coverage(90.2287874528, 1900, "office", "nlos", margin_db=6, area_efficiency=0.70)
        expected = 10 ** ((84.2287874528 - 30.13 - 24 * math.log10(1.9)) / 23.9)
        self.assertAlmostEqual(result["Coverage_Radius_m"], expected, places=9)
        self.assertGreater(result["Planning_Area_sqft"], 0)

    def test_nr_100_mhz_30_khz_at_3700_mhz(self):
        result = convert_mapl_to_coverage(85.8671609824, 3700, "industrial", "nlos", margin_db=6, area_efficiency=0.42)
        self.assertAlmostEqual(result["Coverage_Radius_m"], 37.4110703412, places=7)
        self.assertTrue(result["Distance_Range_Valid"])

    def test_open_office_is_los(self):
        result = classify_los_nlos(open_office())
        self.assertEqual(result["condition"], "los")
        self.assertEqual(result["confidence"], "High")

    def test_dense_industrial_is_nlos(self):
        mapping = map_building_to_itu_environment(dense_industrial())
        condition = classify_los_nlos(dense_industrial())
        self.assertEqual(mapping["environment"], "industrial")
        self.assertEqual(condition["condition"], "nlos")
        self.assertEqual(condition["confidence"], "High")

    def test_warehouse_high_ceiling_is_informational(self):
        record = dense_industrial(
            Sub_Type_A="Warehouse / Storage Area",
            Assumption_Profile="Warehouse",
            Ceiling_Height_Class="High_18_30ft",
        )
        result = calculate_building_coverage(record, mapl("NR", "N77/C-Band", 3750, 40, 30, 106, 89.9757))
        self.assertIn("High ceiling is informational", result["Warnings"])
        self.assertEqual(result["ITU_Environment"], "industrial")

    def test_missing_exact_frequency_uses_known_band(self):
        result = resolve_frequency_mhz({"Band": "B48-CBRS"})
        self.assertEqual(result["frequency_mhz"], 3625.0)
        self.assertEqual(result["source"], "band_center_lookup")

    def test_multiple_bands_select_lowest_planning_area(self):
        building = pd.DataFrame([dense_industrial()])
        results = calculate_coverage_for_all_buildings(
            building,
            [
                mapl("NR", "B48-CBRS", None, 40, 30, 106, 89.0),
                mapl("NR", "N77/C-Band", None, 40, 30, 106, 89.0),
            ],
        )
        limiting = results[results["Is_Limiting_Band"]]
        self.assertEqual(len(limiting), 1)
        self.assertEqual(limiting.iloc[0]["Band"], "N77/C-Band")

    def test_total_loss_is_not_subtracted(self):
        result = calculate_incremental_loss_db({"Total Loss": 12.0})
        self.assertEqual(result["additional_loss_db"], 0.0)
        self.assertEqual(result["source"], "itu_coefficients_only")

    def test_component_losses_are_not_subtracted(self):
        result = calculate_incremental_loss_db({"Total Losses Material": 7.0, "Total Loss Density": 4.0})
        self.assertEqual(result["additional_loss_db"], 0.0)

    def test_total_and_components_do_not_double_count(self):
        result = calculate_incremental_loss_db({"Total Loss": 11.0, "Total Losses Material": 7.0, "Total Loss Density": 4.0})
        self.assertEqual(result["additional_loss_db"], 0.0)
        manual = calculate_incremental_loss_db({"Total Loss": 11.0}, override_db=3.0)
        self.assertEqual(manual["additional_loss_db"], 3.0)

    def test_invalid_percentages_generate_fallback_warnings(self):
        record = open_office(**{"Open_Area_%": 140})
        condition = classify_los_nlos(record)
        efficiency = calculate_area_efficiency(record)
        self.assertEqual(condition["condition"], "nlos")
        self.assertEqual(condition["confidence"], "Low")
        self.assertEqual(efficiency["source"], "layout_default")
        self.assertTrue(efficiency["warnings"])

    def test_missing_environment_uses_warned_fallback(self):
        record = open_office()
        for field in ("Assumption_Profile", "Environment_Type", "Building_Type", "Sub_Type_A"):
            record.pop(field, None)
        mapping = map_building_to_itu_environment(record)
        self.assertEqual(mapping["environment"], "office")
        self.assertEqual(mapping["confidence"], "Low")
        self.assertTrue(mapping["warnings"])

    def test_distance_outside_model_range_is_flagged(self):
        result = convert_mapl_to_coverage(90.23, 1900, "office", "los", margin_db=6, area_efficiency=0.80)
        self.assertFalse(result["Distance_Range_Valid"])
        self.assertEqual(result["Calculation_Status"], "warning_extrapolated")

        self.assertTrue(result["Coverage_Capped_To_Model_Range"])
        self.assertEqual(result["Planning_Coverage_Radius_m"], 27.0)
        self.assertAlmostEqual(
            result["Planning_Area_m2"],
            math.pi * 27.0 ** 2 * 0.80,
        )

    def test_capped_coverage_remains_valid_for_equipment_planning(self):
        result = calculate_building_coverage(
            open_office(**{"Coverage Area": 100_000}),
            mapl(frequency_mhz=1900),
            margin_db=6,
        )
        self.assertFalse(result["Distance_Range_Valid"])
        self.assertTrue(result["Coverage_Capped_To_Model_Range"])
        self.assertTrue(result["Result_Valid_For_Planning"])
        self.assertGreater(result["Number_of_required_DOTs_Radios"], 0)
        self.assertIn("planning coverage was capped", result["Warnings"])

    def test_margin_change_is_applied_once(self):
        baseline = convert_mapl_to_coverage(80, 3700, "industrial", "nlos", margin_db=6, area_efficiency=0.50)
        higher_margin = convert_mapl_to_coverage(80, 3700, "industrial", "nlos", margin_db=10, area_efficiency=0.50)
        self.assertLess(higher_margin["Coverage_Radius_m"], baseline["Coverage_Radius_m"])
        expected_ratio = 10 ** (-4 / (10 * 2.80))
        self.assertAlmostEqual(higher_margin["Coverage_Radius_m"] / baseline["Coverage_Radius_m"], expected_ratio, places=9)

    def test_batch_supports_lte_and_nr_and_stable_schema(self):
        results = calculate_coverage_for_all_buildings(
            pd.DataFrame([dense_industrial()]),
            [
                mapl("LTE", "B2/B25", 1962.5, 20, 15, 100, 90.23),
                mapl("NR", "N77/C-Band", 3750, 100, 30, 273, 85.87),
            ],
        )
        self.assertEqual(set(results["Coverage_Type"]), {"lte_coverage", "nr_coverage"})
        self.assertEqual(list(results.columns), RESULT_COLUMNS)

    def test_band_center_frequency_mapping(self):
        self.assertEqual(BAND_CENTER_FREQUENCY_MHZ, {
            "B48-CBRS": 3625.0,
            "B2/B25": 1962.5,
            "B4/B66": 2155.0,
            "N77/C-Band": 3750.0,
        })

    def test_coverage_type_and_rd4455_power_rules(self):
        self.assertEqual(resolve_technology("Enterprise Private 5G"), "NR")
        self.assertEqual(resolve_technology("Enterprise 5G Coverage", "4G"), "LTE")
        self.assertEqual(resolve_technology("Enterprise 5G Coverage", "5G"), "NR")
        self.assertEqual(resolve_radio_power_mw("RD4455", "B4/B66"), 200.0)
        self.assertEqual(resolve_radio_power_mw("DOT 4455", "B48-CBRS"), 200.0)
        self.assertEqual(resolve_radio_power_mw("RD4455", "N77/C-Band"), 400.0)
        self.assertEqual(resolve_radio_power_mw("RD4459", "B4/B66"), 400.0)


if __name__ == "__main__":
    unittest.main()
