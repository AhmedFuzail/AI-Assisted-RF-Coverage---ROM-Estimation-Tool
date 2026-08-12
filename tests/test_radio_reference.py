import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pandas as pd

from coverage_engine import calculate_building_coverage, calculate_coverage_for_all_buildings
from radio_reference import (
    DATA_SOURCE,
    RADIO_REFERENCE_PATH,
    build_radio_mapl_config,
    calculate_mapl,
    get_radio_dot_characteristics,
    get_radio_dot_models,
    load_radio_dot_reference,
    normalize_band,
    normalize_dot_model,
    normalize_radio_model,
    normalize_variant_kry,
)


def radio_config(model, variant, band, technology, **updates):
    characteristics = get_radio_dot_characteristics(model, variant, band, technology)
    inputs = {
        "dot_model": model,
        "dot_variant_kry": variant,
        "band": band,
        "technology": technology,
        "target_rsrp_dbm": -95,
        "margin_db": 6,
        "carrier_count": 1,
    }
    inputs.update(updates)
    return build_radio_mapl_config(inputs, radio_reference=characteristics)


def open_office():
    return {
        "Building_ID": "building-1",
        "Building_Name": "Reference Office",
        "Building_Type": "Office",
        "Category": "Open Office",
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
        "Assumption_Profile": "Office_Open",
    }


class RadioReferenceTests(unittest.TestCase):
    def test_dot_2274_b25_unique_inference(self):
        result = get_radio_dot_characteristics("2274", None, "PCS", "LTE")
        self.assertEqual(result.dot_model, "DOT 2274")
        self.assertEqual(result.dot_variant_kry, "KRY 901 468/1")
        self.assertEqual(result.default_tx_power_dbm_per_branch, 23)
        self.assertEqual(result.antenna_gain_dbi, 1.3)
        self.assertEqual(result.tx_branch_count, 2)
        self.assertEqual(result.duplex_mode, "FDD")

    def test_dot_4459_b48_unique_inference_and_sas_warning(self):
        result = get_radio_dot_characteristics("Radio Dot 4459", None, "B48-CBRS", "5G")
        self.assertEqual(result.dot_variant_kry, "KRY 901 516/1")
        self.assertEqual(result.default_tx_power_dbm_per_branch, 26)
        self.assertEqual(result.antenna_gain_dbi, 5.3)
        self.assertEqual(result.tx_branch_count, 4)
        self.assertEqual(result.duplex_mode, "TDD")
        self.assertIn("SAS-authorized", " ".join(result.warnings))

    def test_micro_4402_b25_unique_inference(self):
        result = get_radio_dot_characteristics("Micro_4402", None, "B25", "LTE")
        self.assertEqual(result.dot_model, "Micro Radio 4402")
        self.assertEqual(result.dot_variant_kry, "KRC 161 737/1")
        self.assertEqual(result.default_tx_power_dbm_per_branch, 37)
        self.assertEqual(result.antenna_gain_dbi, 9.2)
        self.assertEqual(result.tx_branch_count, 4)
        self.assertEqual(result.duplex_mode, "FDD")

    def test_micro_4402_b66_resolves_krc_variant(self):
        result = get_radio_dot_characteristics("Micro Radio 4402", None, "AWS", "NR")
        self.assertEqual(result.dot_variant_kry, "KRC 161 738/1")
        self.assertEqual(result.default_tx_power_dbm_per_branch, 37)
        self.assertEqual(result.antenna_gain_dbi, 8.5)

    def test_micro_4408_b48_uses_rf_table_and_sas_warning(self):
        result = get_radio_dot_characteristics("Micro4408", None, "CBRS", "5G")
        self.assertEqual(result.dot_model, "Micro Radio 4408")
        self.assertEqual(result.dot_variant_kry, "KRC 161 746/1")
        self.assertEqual(result.default_tx_power_dbm_per_branch, 37)
        self.assertEqual(result.antenna_gain_dbi, 12.06)
        self.assertEqual(result.tx_branch_count, 4)
        self.assertEqual(result.duplex_mode, "TDD")
        self.assertIn("SAS-authorized", " ".join(result.warnings))

    def test_reference_model_list_includes_micro_radios(self):
        self.assertIn("Micro Radio 4402", get_radio_dot_models())
        self.assertIn("Micro Radio 4408", get_radio_dot_models())

    def test_dot_4455_b77d_requires_variant(self):
        with self.assertRaisesRegex(ValueError, "more than one hardware variant"):
            get_radio_dot_characteristics("DOT4455", None, "N77/C-Band", "NR")

    def test_dot_4455_b77d_kry_523(self):
        result = get_radio_dot_characteristics("DOT 4455", "KRY 901 523/1", "B77D", "NR")
        self.assertEqual(result.default_tx_power_dbm_per_branch, 26)
        self.assertEqual(result.antenna_gain_dbi, 4.3)
        self.assertEqual(result.tx_branch_count, 4)
        self.assertIn("power mismatch", " ".join(result.warnings))

    def test_dot_4455_b77d_kry_551(self):
        result = get_radio_dot_characteristics("DOT 4455", "KRY 901 551/1", "B77D", "NR")
        self.assertEqual(result.default_tx_power_dbm_per_branch, 26)
        self.assertEqual(result.antenna_gain_dbi, 5.39)
        self.assertEqual(result.tx_branch_count, 4)

    def test_lte_rejected_for_nr_only_row(self):
        with self.assertRaisesRegex(ValueError, "LTE is not supported"):
            get_radio_dot_characteristics("DOT 4455", "KRY 901 523/1", "B77D", "LTE")

    def test_normalization_aliases(self):
        self.assertEqual(normalize_dot_model("RD4455"), "DOT 4455")
        self.assertEqual(normalize_dot_model("Radio Dot 4455"), "DOT 4455")
        self.assertEqual(normalize_radio_model("Micro_4408"), "Micro Radio 4408")
        self.assertEqual(normalize_radio_model("Micro Radio 4402"), "Micro Radio 4402")
        self.assertEqual(normalize_variant_kry("KRC161 746/1"), "KRC 161 746/1")
        self.assertEqual(normalize_band("Band 25"), "B25")
        self.assertEqual(normalize_band("B4/B66"), "B66")
        self.assertEqual(normalize_band("N77/C-Band"), "B77D")

    def test_user_tx_power_overrides_table_default(self):
        config = radio_config(
            "DOT 4459",
            None,
            "B48",
            "NR",
            configured_tx_power_dbm_per_branch=20,
        )
        result = calculate_mapl(config)
        self.assertEqual(result["Configured_Tx_Power_dBm_per_Branch"], 20)
        self.assertIn("configured_tx_power_dbm_per_branch", result["Override_Fields"])
        self.assertIn("user-configured", result["Warnings"])

    def test_antenna_gain_is_added_exactly_once(self):
        config = radio_config("DOT 2274", None, "B25", "LTE")
        with_gain = calculate_mapl(config)
        without_gain = calculate_mapl(replace(config, antenna_gain_dbi=0))
        self.assertAlmostEqual(with_gain["Branch_EIRP_dBm"], 24.3, places=9)
        self.assertAlmostEqual(
            with_gain["MAPL_Before_Margin_dB"] - without_gain["MAPL_Before_Margin_dB"],
            1.3,
            places=9,
        )

    def test_branch_count_is_not_mapl_gain(self):
        config = radio_config("DOT 4459", None, "B48", "NR")
        original = calculate_mapl(config)
        changed_branch_count = calculate_mapl(replace(config, tx_branch_count=8))
        self.assertEqual(original["MAPL_Before_Margin_dB"], changed_branch_count["MAPL_Before_Margin_dB"])

    def test_margin_is_applied_once(self):
        config = radio_config("DOT 4455", "KRY 901 523/1", "B66", "LTE")
        result = calculate_mapl(config)
        self.assertAlmostEqual(result["Final_MAPL_dB"], result["MAPL_Before_Margin_dB"] - 6, places=9)
        coverage = calculate_building_coverage(open_office(), result, margin_db=6)
        self.assertAlmostEqual(
            coverage["Usable_MAPL_dB"],
            result["MAPL_Before_Margin_dB"] - 6 - coverage["Additional_Loss_dB"],
            places=9,
        )

    def test_selected_frequency_reaches_coverage_model(self):
        config = radio_config(
            "DOT 4459",
            None,
            "B48",
            "NR",
            carrier_frequency_mhz=3600,
        )
        result = calculate_mapl(config)
        coverage = calculate_building_coverage(open_office(), result, margin_db=6)
        self.assertEqual(result["Frequency_MHz"], 3600)
        self.assertEqual(coverage["Frequency_MHz"], 3600)
        self.assertEqual(coverage["Dot_Model"], "DOT 4459")
        self.assertEqual(coverage["Radio_Data_Source"], DATA_SOURCE)

    def test_power_is_shared_only_when_explicit(self):
        base = radio_config("DOT 4459", None, "B48", "NR", carrier_count=2)
        unshared = calculate_mapl(base)
        shared = calculate_mapl(replace(base, power_is_total_across_carriers=True))
        self.assertEqual(unshared["Carrier_Sharing_Loss_dB"], 0)
        self.assertAlmostEqual(shared["Carrier_Sharing_Loss_dB"], 10 * math.log10(2), places=9)
        self.assertAlmostEqual(
            unshared["MAPL_Before_Margin_dB"] - shared["MAPL_Before_Margin_dB"],
            10 * math.log10(2),
            places=9,
        )

    def test_operator_count_controls_power_split_independently_of_carrier_count(self):
        config = radio_config(
            "DOT 4459",
            None,
            "B48",
            "NR",
            carrier_count=1,
            Operator_count=3,
        )

        result = calculate_mapl(config)

        self.assertEqual(result["Carrier_Count"], 1)
        self.assertEqual(result["Power_Share_Count"], 3)
        self.assertTrue(result["Power_Is_Total_Across_Carriers"])
        self.assertAlmostEqual(result["Carrier_Sharing_Loss_dB"], 10 * math.log10(3), places=9)

    def test_carrier_frequency_range_validation(self):
        with self.assertRaisesRegex(ValueError, "outside the supported B48 range"):
            radio_config("DOT 4459", None, "B48", "NR", carrier_frequency_mhz=3500)

    def test_bandwidth_and_scs_validation(self):
        with self.assertRaisesRegex(ValueError, "Unsupported LTE bandwidth"):
            radio_config("DOT 2274", None, "B25", "LTE", bandwidth_mhz=40)
        with self.assertRaisesRegex(ValueError, "Unsupported NR bandwidth/SCS combination"):
            radio_config("DOT 4459", None, "B48", "NR", bandwidth_mhz=5, scs_khz=60)

    def test_carrier_count_validation(self):
        with self.assertRaisesRegex(ValueError, "positive whole number"):
            radio_config("DOT 4459", None, "B48", "NR", carrier_count=0)

    def test_duplicate_reference_rows_are_rejected(self):
        source = RADIO_REFERENCE_PATH.read_text(encoding="utf-8")
        duplicate = source + source.splitlines()[1] + "\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "duplicate.csv"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate or conflicting radio RF reference row"):
                load_radio_dot_reference(path)

    def test_numerical_regressions(self):
        cases = [
            ("DOT 2274", None, "B25", "LTE", 88.50818753952376),
            ("DOT 4455", "KRY 901 523/1", "B66", "LTE", 91.50818753952376),
            ("DOT 4455", "KRY 901 523/1", "B77D", "NR", 94.25512888687605),
            ("DOT 4459", None, "B48", "NR", 95.25512888687605),
            ("DOT 4459", None, "B77D", "NR", 95.35512888687605),
            ("Micro Radio 4402", None, "B25", "LTE", 110.40818753952375),
            ("Micro Radio 4402", None, "B66", "NR", 109.45512888687605),
            ("Micro Radio 4408", None, "B48", "NR", 113.01512888687606),
        ]
        for model, variant, band, technology, expected_mapl in cases:
            with self.subTest(model=model, variant=variant, band=band, technology=technology):
                result = calculate_mapl(radio_config(model, variant, band, technology))
                self.assertAlmostEqual(result["MAPL_Before_Margin_dB"], expected_mapl, places=9)

    def test_batch_coverage_accepts_lte_and_nr_radio_results(self):
        lte = calculate_mapl(radio_config("DOT 2274", None, "B25", "LTE"))
        nr = calculate_mapl(radio_config("DOT 4459", None, "B48", "NR"))
        results = calculate_coverage_for_all_buildings(pd.DataFrame([open_office()]), [lte, nr], margin_db=6)
        self.assertEqual(set(results["Coverage_Type"]), {"lte_coverage", "nr_coverage"})
        self.assertEqual(set(results["Dot_Model"]), {"DOT 2274", "DOT 4459"})


if __name__ == "__main__":
    unittest.main()
