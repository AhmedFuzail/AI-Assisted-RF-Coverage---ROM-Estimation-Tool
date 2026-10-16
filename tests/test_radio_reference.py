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
    default_bandwidth_mhz,
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

    def test_new_dot_and_macro_radio_reference_rows(self):
        b77s = get_radio_dot_characteristics("DOT 4459", None, "B77S", "NR")
        self.assertEqual(b77s.dot_variant_kry, "KRY 901 590/1")
        self.assertEqual(b77s.default_tx_power_dbm_per_branch, 27)
        self.assertEqual(b77s.antenna_gain_dbi, 5.4)

        b78a = get_radio_dot_characteristics("DOT 4479", None, "B78A", "LTE")
        self.assertEqual((b78a.frequency_min_mhz, b78a.frequency_max_mhz), (3300, 3600))
        self.assertEqual(b78a.tx_branch_count, 4)
        self.assertEqual(b78a.antenna_gain_dbi, 5.4)
        b78l = get_radio_dot_characteristics("DOT 4479", None, "B78L", "NR")
        existing = get_radio_dot_characteristics("DOT 4459", None, "B77D", "NR")
        for row in (b77s, b78a, b78l):
            self.assertEqual(row.antenna_gain_dbi, existing.antenna_gain_dbi)
            self.assertIn("planning antenna gain", row.power_note)
            if row.band == "B77S":
                self.assertNotIn(row.power_note, row.warnings)
            else:
                self.assertIn("planning antenna gain", " ".join(row.warnings))
            self.assertNotIn("placeholder", " ".join(row.warnings))

        b40 = get_radio_dot_characteristics("Radio 4461HP", None, "B40", "NR")
        self.assertEqual(b40.dot_model, "Radio 4461HP")
        self.assertEqual(b40.dot_variant_kry, "KRC 161 0077/11")
        self.assertAlmostEqual(b40.default_tx_power_dbm_per_branch, 47.78)

        b28 = get_radio_dot_characteristics("Radio 2271", None, "B28", "LTE")
        self.assertEqual(b28.dot_model, "Radio 2271")
        self.assertEqual(b28.tx_branch_count, 2)
        self.assertAlmostEqual(b28.default_tx_power_dbm_per_branch, 49.03)

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
        self.assertEqual(normalize_radio_model("Radio 4461HP"), "Radio 4461HP")
        self.assertEqual(normalize_radio_model("Radio 2271"), "Radio 2271")
        self.assertEqual(normalize_radio_model("2271"), "Radio 2271")
        self.assertEqual(normalize_variant_kry("KRC161 746/1"), "KRC 161 746/1")
        self.assertEqual(normalize_band("Band 25"), "B25")
        self.assertEqual(normalize_band("B4/B66"), "B66")
        self.assertEqual(normalize_band("N77/C-Band"), "B77D")
        self.assertEqual(normalize_band("n40"), "B40")
        self.assertEqual(normalize_band("700 MHz"), "B28")

    def test_band_specific_default_bandwidths(self):
        self.assertEqual(default_bandwidth_mhz("N77/C-Band", "NR"), 80.0)
        self.assertEqual(default_bandwidth_mhz("B77G", "5G"), 80.0)
        self.assertEqual(default_bandwidth_mhz("B78A", "5G"), 80.0)
        self.assertEqual(default_bandwidth_mhz("B25", "LTE"), 20.0)
        self.assertEqual(default_bandwidth_mhz("B25", "NR"), 20.0)
        self.assertEqual(default_bandwidth_mhz("B66", "4G"), 20.0)
        self.assertEqual(default_bandwidth_mhz("B66", "5G"), 20.0)
        self.assertEqual(default_bandwidth_mhz("B48", "NR"), 40.0)

        n77 = radio_config("DOT 4459", None, "B77D", "NR")
        b25_lte = radio_config("DOT 2274", None, "B25", "LTE")
        b25_nr = radio_config("DOT 2274", None, "B25", "NR")
        b66_lte = radio_config("DOT 2274", None, "B66", "LTE")
        b66_nr = radio_config("DOT 2274", None, "B66", "NR")
        explicit_override = radio_config(
            "DOT 4459",
            None,
            "B77D",
            "NR",
            bandwidth_mhz=40,
        )

        self.assertEqual(n77.bandwidth_mhz, 80.0)
        self.assertEqual(b25_lte.bandwidth_mhz, 20.0)
        self.assertEqual(b25_nr.bandwidth_mhz, 20.0)
        self.assertEqual(b66_lte.bandwidth_mhz, 20.0)
        self.assertEqual(b66_nr.bandwidth_mhz, 20.0)
        self.assertEqual(explicit_override.bandwidth_mhz, 40.0)

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

    def test_private_5g_fixes_40_mhz_for_every_nr_radio_reference(self):
        for row in load_radio_dot_reference():
            if "NR" not in row.supported_technologies:
                continue
            for source in ("user", "project"):
                with self.subTest(model=row.dot_model, variant=row.dot_variant_kry, band=row.band, source=source):
                    inputs = {
                        "technology": "NR", "Operator_type": "Enterprise Private 5G",
                        "target_rsrp_dbm": -95,
                    }
                    calculated = {}
                    if source == "user":
                        inputs["bandwidth_mhz"] = 80
                    else:
                        calculated["bandwidth_mhz"] = 80
                    config = build_radio_mapl_config(inputs, calculated, radio_reference=row)
                    self.assertEqual(config.bandwidth_mhz, 40)
                    self.assertEqual(calculate_mapl(config)["RB_Count"], 106)
                    self.assertEqual(config.value_sources["bandwidth_mhz"], "Enterprise Private 5G fixed bandwidth policy")
                    self.assertNotIn("bandwidth_mhz", config.override_fields)
        self.assertEqual(default_bandwidth_mhz("B77S", "NR", "Enterprise Private 5G"), 40)
        public = radio_config("DOT 4455", "KRY 901 523/1", "B77D", "NR", Operator_type="Enterprise 5G Coverage")
        self.assertEqual(public.bandwidth_mhz, 80)

    def test_enterprise_additions_reach_mapl_and_coverage(self):
        cases = [
            ("DOT 4459", "B77S", 4000, 27, 5.4),
            ("DOT 4479", "B78A", 3450, 24, 5.4),
            ("DOT 4479", "B78L", 3650, 24, 5.4),
            ("Radio 4461HP", "B40", 2350, 47.78, 0),
            ("Radio 2271", "B28", 780.5, 49.03, 0),
        ]
        for model, band, frequency, power, gain in cases:
            for technology in (("NR",) if band == "B77S" else ("LTE", "NR")):
                with self.subTest(model=model, band=band, technology=technology):
                    config = radio_config(
                        model, None, band, technology,
                        Operator_type="Enterprise 5G Coverage", Operator_count=3,
                    )
                    result = calculate_mapl(config)
                    expected_power = power - 10 * math.log10(3)
                    if model == "DOT 4459":
                        expected_power = min(expected_power, 23)
                    rb_count = 100 if technology == "LTE" else (217 if band.startswith(("B77", "B78")) else 51 if band == "B28" else 106)
                    expected_mapl = expected_power + gain - 10 * math.log10(12 * rb_count) + 95
                    self.assertEqual(result["Frequency_MHz"], frequency)
                    self.assertEqual(result["RB_Count"], rb_count)
                    self.assertAlmostEqual(result["MAPL_Before_Margin_dB"], expected_mapl)
                    self.assertAlmostEqual(result["Final_MAPL_dB"], expected_mapl - 6)
                    coverage = calculate_building_coverage(open_office(), result, margin_db=6)
                    self.assertTrue(coverage["Result_Valid_For_Planning"])
                    self.assertEqual(coverage["Band"], band)
                    self.assertEqual(coverage["Frequency_MHz"], frequency)
                    self.assertAlmostEqual(coverage["Usable_MAPL_dB"], expected_mapl - 6)
                    self.assertGreater(coverage["Number_of_required_DOTs_Radios"], 0)
                    if band == "B77S":
                        self.assertNotIn("500 mW per branch", result["Warnings"])
                        self.assertNotIn("500 mW per branch", coverage["Warnings"])
                    elif model == "DOT 4479":
                        self.assertIn("planning antenna gain", result["Warnings"])
                    elif model.startswith("Radio "):
                        self.assertIn("external antenna gain", result["Warnings"])

    def test_macro_radio_power_validation_uses_reference_rating(self):
        for model, band, rating in [("Radio 4461HP", "B40", 47.78), ("Radio 2271", "B28", 49.03)]:
            with self.subTest(model=model):
                config = radio_config(model, None, band, "NR", configured_tx_power_dbm_per_branch=rating)
                self.assertEqual(config.configured_tx_power_dbm_per_branch, rating)
                with self.assertRaisesRegex(ValueError, "configured_tx_power"):
                    radio_config(model, None, band, "NR", configured_tx_power_dbm_per_branch=rating + 0.01)
        with self.assertRaisesRegex(ValueError, "between -10 and 40"):
            radio_config("DOT 4459", None, "B77S", "NR", configured_tx_power_dbm_per_branch=41)

    def test_b78_lte_defaults_and_invalid_bandwidth_override(self):
        for band in ("B78A", "B78L"):
            with self.subTest(band=band):
                self.assertEqual(radio_config("DOT 4479", None, band, "LTE").bandwidth_mhz, 20)
                with self.assertRaisesRegex(ValueError, "Unsupported LTE bandwidth"):
                    radio_config("DOT 4479", None, band, "LTE", bandwidth_mhz=80)

    def test_dot_4459_power_cap_is_applied_after_operator_sharing(self):
        public = calculate_mapl(radio_config(
            "DOT 4459", None, "B41K", "NR",
            Operator_type="Enterprise 5G Coverage",
        ))
        private = calculate_mapl(radio_config(
            "DOT 4459", None, "B48", "NR",
            Operator_type="Enterprise Private 5G",
        ))
        public_shared = calculate_mapl(radio_config(
            "DOT 4459", None, "B41K", "NR",
            Operator_type="Enterprise 5G Coverage",
            Operator_count=2,
        ))
        private_shared = calculate_mapl(radio_config(
            "DOT 4459", None, "B48", "NR",
            Operator_type="Enterprise Private 5G",
            Operator_count=2,
        ))
        override_shared = calculate_mapl(radio_config(
            "DOT 4459", None, "B41K", "NR",
            Operator_type="Enterprise 5G Coverage",
            Operator_count=2,
            configured_tx_power_dbm_per_branch=30,
        ))
        lower_power = calculate_mapl(radio_config(
            "DOT 4459", None, "B41K", "NR",
            Operator_type="Enterprise 5G Coverage",
            configured_tx_power_dbm_per_branch=20,
        ))

        self.assertEqual(public["Configured_Tx_Power_dBm_per_Branch"], 26)
        self.assertEqual(private["Configured_Tx_Power_dBm_per_Branch"], 26)
        self.assertEqual(public["Effective_Tx_Power_dBm_per_Branch"], 23)
        self.assertEqual(private["Effective_Tx_Power_dBm_per_Branch"], 23)
        expected_shared_power = 26 - 10 * math.log10(2)
        self.assertAlmostEqual(
            public_shared["Effective_Tx_Power_dBm_per_Branch"],
            expected_shared_power,
            places=9,
        )
        self.assertAlmostEqual(
            private_shared["Effective_Tx_Power_dBm_per_Branch"],
            expected_shared_power,
            places=9,
        )
        self.assertEqual(override_shared["Effective_Tx_Power_dBm_per_Branch"], 23)
        self.assertEqual(lower_power["Effective_Tx_Power_dBm_per_Branch"], 20)
        self.assertIn("after operator power sharing", public["Warnings"].lower())
        self.assertEqual(
            public["Power_Source"],
            "Deployment power cap applied after operator sharing",
        )

    def test_enterprise_coverage_dot_4455_n77_cap_is_after_sharing(self):
        single_operator = calculate_mapl(radio_config(
            "DOT 4455", "KRY 901 523/1", "B77D", "NR",
            Operator_type="Enterprise 5G Coverage",
        ))
        two_operators = calculate_mapl(radio_config(
            "DOT 4455", "KRY 901 523/1", "B77D", "NR",
            Operator_type="Enterprise 5G Coverage",
            Operator_count=2,
        ))
        private = calculate_mapl(radio_config(
            "DOT 4455", "KRY 901 523/1", "B77D", "NR",
            Operator_type="Enterprise Private 5G",
        ))
        public_b66 = calculate_mapl(radio_config(
            "DOT 4455", "KRY 901 523/1", "B66", "NR",
            Operator_type="Enterprise 5G Coverage",
        ))

        self.assertEqual(single_operator["Configured_Tx_Power_dBm_per_Branch"], 26)
        self.assertEqual(single_operator["Effective_Tx_Power_dBm_per_Branch"], 24)
        self.assertAlmostEqual(
            two_operators["Effective_Tx_Power_dBm_per_Branch"],
            26 - 10 * math.log10(2),
            places=9,
        )
        self.assertEqual(private["Effective_Tx_Power_dBm_per_Branch"], 26)
        self.assertEqual(public_b66["Effective_Tx_Power_dBm_per_Branch"], 23)
        self.assertIn("DOT 4455 N77", single_operator["Warnings"])

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
            ("DOT 4455", "KRY 901 523/1", "B77D", "NR", 91.14359020103846),
            ("DOT 4459", None, "B48", "NR", 95.25512888687605),
            ("DOT 4459", None, "B77D", "NR", 92.24359020103846),
            ("Micro Radio 4402", None, "B25", "LTE", 110.40818753952375),
            ("Micro Radio 4402", None, "B66", "NR", 112.63248577854438),
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
