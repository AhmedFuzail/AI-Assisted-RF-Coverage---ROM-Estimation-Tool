"""Exercise deployment, technology, and radio-band choices in both Streamlit UIs."""

import math
import os
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

from radio_selection import compatible_radio_choices, deployment_allowed_bands


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_CHOICES = [
    "DOT 4459 : B77S", "DOT 4479 : B78A", "DOT 4479 : B78L", "DOT 4459 : B48",
]
PRIVATE_CASES = [
    ("DOT 4459", "B77S", "KRY 901 590/1", 4000, 5.4),
    ("DOT 4479", "B78A", "KRY 901 431/1", 3450, 5.4),
    ("DOT 4479", "B78L", "KRY 901 433/1", 3650, 5.4),
    ("DOT 4459", "B48", "KRY 901 516/1", 3625, 5.3),
]


class EnterpriseRadioIntakeTests(unittest.TestCase):
    def setUp(self):
        previous_cwd = Path.cwd()
        os.chdir(REPO_ROOT)
        self.addCleanup(os.chdir, previous_cwd)

    def assert_app_ok(self, app):
        self.assertEqual([error.message for error in app.exception], [])
        self.assertEqual([error.value for error in app.error], [])

    def click(self, app, label):
        next(button for button in app.button if button.label == label).click().run()
        self.assert_app_ok(app)

    def complete_intake(self, app, answers, *, private=False):
        for _ in range(23):
            self.assert_app_ok(app)
            if any(button.label == "Run RF calculations" for button in app.button):
                return app
            for widget in app.text_input:
                if widget.label in answers:
                    widget.set_value(answers[widget.label])
            for widget in app.selectbox:
                if widget.label == "Coverage Type":
                    self.assertFalse(private)
                    self.assertEqual(widget.options, ["4G", "5G"])
                if widget.label == "Radio Model":
                    self.initial_radio_options = list(widget.options)
                    if private and app.session_state["rf_intake_data"].get("sol_type") == "DOT-IRU-BBU":
                        self.assertEqual(widget.options, PRIVATE_CHOICES)
                    else:
                        self.assertFalse(any("4459" in choice or "4479" in choice for choice in widget.options))
                if widget.label in answers:
                    self.field_steps[widget.label] = app.session_state["rf_intake_step"]
                    widget.select(answers[widget.label])
            for widget in app.select_slider:
                if widget.label == "Operators on Highest Band":
                    widget.set_value(3)
            self.click(app, "Save changes" if app.session_state["rf_intake_edit_mode"] else "Save and continue")
        self.fail("The guided intake did not complete")

    def guided_intake(self, filename, model, band, variant, *, private=False, coverage="5G"):
        app = AppTest.from_file(str(REPO_ROOT / filename), default_timeout=30).run()
        self.field_steps = {}
        self.answers = {
            "Customer Name": "Radio deployment regression",
            "Venue Name": "Test office",
            "Total Sq.Ft Coverage": "100000",
            "Number of Floors": "1",
            "General Building Type": "Office",
            "Building Category": "Open_Office",
            "Use Case Type": "Coverage Focused",
            "Equipment Type": "Micro-BBU" if model.startswith("Micro Radio") else "Radio-BBU" if model.startswith("Radio ") else "DOT-IRU-BBU",
            "Operator Type": "Enterprise Private 5G" if private else "Enterprise 5G Coverage",
            "Coverage Type": coverage,
            "Radio Model": f"{model} : {band}" if private and model.startswith("DOT ") else model,
            "Hardware Variant": variant,
            "Highest Frequency Band": band,
        }
        return self.complete_intake(app, self.answers, private=private)

    def edit_field(self, app, label):
        self.click(app, "Modify intake")
        app.selectbox(key="rf_intake_edit_field").select(self.field_steps[label]).run()
        self.click(app, "Edit selected field")

    def test_private_dot_choices_calculate_in_both_uis(self):
        for filename in ("main.py", "simplified_ui.py"):
            for model, band, variant, frequency, gain in PRIVATE_CASES:
                with self.subTest(ui=filename, model=model, band=band):
                    app = self.guided_intake(filename, model, band, variant, private=True)
                    self.click(app, "Run RF calculations")
                    result = app.session_state["mapl_result"]
                    self.assertEqual(result["Dot_Model"], model)
                    self.assertEqual(result["Dot_Variant_KRY"], variant)
                    self.assertEqual(result["Band"], band)
                    self.assertEqual(result["Frequency_MHz"], frequency)
                    self.assertEqual(result["Antenna_Gain_dBi"], gain)
                    self.assertEqual(result["Power_Share_Count"], 1)
                    self.assertEqual(result["Carrier_Sharing_Loss_dB"], 0)
                    self.assertEqual(result["Technology"], "NR")
                    self.assertEqual(result["Bandwidth_MHz"], 40)
                    self.assertEqual(result["RB_Count"], 106)
                    self.assertEqual(result["Target_RSRP_dBm"], -95)
                    rows = app.session_state["coverage_result_df"]
                    self.assertTrue(rows["Result_Valid_For_Planning"].all())
                    self.assertTrue(rows["Band"].eq(band).all())
                    self.assertTrue(rows["Frequency_MHz"].eq(frequency).all())
                    self.assertTrue(rows["Antenna_Gain_dBi"].eq(gain).all())
                    self.assertTrue(rows["Number_of_required_DOTs_Radios"].gt(0).all())
                    self.click(app, "Modify intake")
                    self.assertFalse(any("Coverage Type" in value for value in app.selectbox(key="rf_intake_edit_field").options))

    def test_public_macro_radios_support_4g_and_5g(self):
        for filename in ("main.py", "simplified_ui.py"):
            for model, band, variant in [("Radio 4461HP", "B40", "KRC 161 0077/11"), ("Radio 2271", "B28", "KRC 161 2228/11")]:
                for coverage in ("4G", "5G"):
                    with self.subTest(ui=filename, model=model, coverage=coverage):
                        app = self.guided_intake(filename, model, band, variant, coverage=coverage)
                        self.click(app, "Run RF calculations")
                        result = app.session_state["mapl_result"]
                        self.assertEqual(result["Technology"], "LTE" if coverage == "4G" else "NR")
                        self.assertEqual(result["Power_Share_Count"], 3)
                        self.assertAlmostEqual(result["Carrier_Sharing_Loss_dB"], 10 * math.log10(3))
                        self.assertTrue(app.session_state["coverage_result_df"]["Result_Valid_For_Planning"].all())
                        labels = [metric.label for metric in app.metric]
                        self.assertIn("Total required Radios", labels)
                        self.assertNotIn("Total IRUs", labels)
                        self.assertNotIn("Total BBUs", labels)
                        if filename == "main.py":
                            next(item for item in app.checkbox if item.label == "Override Tx power per branch").check().run()
                            self.assert_app_ok(app)

    def test_private_model_band_edit_clears_old_results(self):
        for filename in ("main.py", "simplified_ui.py"):
            with self.subTest(ui=filename):
                app = self.guided_intake(filename, *PRIVATE_CASES[1][:3], private=True)
                self.click(app, "Run RF calculations")
                self.edit_field(app, "Radio Model")
                next(widget for widget in app.selectbox if widget.label == "Radio Model").select("DOT 4479 : B78L")
                self.click(app, "Save changes")
                self.assertIsNone(app.session_state["mapl_result"])
                self.assertIsNone(app.session_state["coverage_result_df"])
                self.assertEqual(app.session_state["rf_intake_data"]["dot_variant_kry"], "KRY 901 433/1")
                self.assertEqual(app.session_state["rf_intake_data"]["Limit_freq_type"], "B78L")
                self.click(app, "Run RF calculations")
                self.assertEqual(app.session_state["mapl_result"]["Frequency_MHz"], 3650)

    def test_public_coverage_edit_updates_technology_and_filters(self):
        for filename in ("main.py", "simplified_ui.py"):
            with self.subTest(ui=filename):
                app = self.guided_intake(filename, "DOT 4455", "B41", "KRY 901 551/1", coverage="4G")
                self.click(app, "Run RF calculations")
                self.assertEqual(app.session_state["mapl_result"]["Technology"], "LTE")
                self.edit_field(app, "Coverage Type")
                next(widget for widget in app.selectbox if widget.label == "Coverage Type").select("5G")
                self.click(app, "Save changes")
                self.assertIsNone(app.session_state["mapl_result"])
                self.complete_intake(app, self.answers | {"Coverage Type": "5G"})
                self.click(app, "Run RF calculations")
                self.assertEqual(app.session_state["mapl_result"]["Technology"], "NR")
                self.edit_field(app, "Radio Model")
                options = next(widget for widget in app.selectbox if widget.label == "Radio Model").options
                self.assertFalse(any("4459" in option or "4479" in option for option in options))

    def test_private_and_public_dot_choices_are_disjoint(self):
        private = {"sol_type": "DOT-IRU-BBU", "Operator_type": "Enterprise Private 5G"}
        self.assertEqual(compatible_radio_choices(private, "NR"), PRIVATE_CHOICES)
        self.assertEqual(deployment_allowed_bands(private), {"B77S", "B78A", "B78L", "B48"})
        for technology in ("LTE", "NR"):
            public = dict(private, Operator_type="Enterprise 5G Coverage")
            self.assertEqual(compatible_radio_choices(public, technology), ["DOT 2274", "DOT 4455"])
            self.assertEqual(deployment_allowed_bands(public | {"dot_type": "DOT 4459"}), set())
            self.assertEqual(deployment_allowed_bands(public | {"dot_type": "DOT 4479"}), set())

    def test_private_to_public_operator_edit_clears_private_radio(self):
        for filename in ("main.py", "simplified_ui.py"):
            with self.subTest(ui=filename):
                app = self.guided_intake(filename, *PRIVATE_CASES[0][:3], private=True)
                self.click(app, "Run RF calculations")
                self.edit_field(app, "Operator Type")
                next(widget for widget in app.selectbox if widget.label == "Operator Type").select("Enterprise 5G Coverage")
                self.click(app, "Save changes")
                intake = app.session_state["rf_intake_data"]
                for key in ("dot_type", "dot_variant_kry", "Limit_freq_type", "radio_model_band"):
                    self.assertNotIn(key, intake)
                self.assertIsNone(app.session_state["mapl_result"])
                self.complete_intake(app, self.answers | {"Operator Type": "Enterprise 5G Coverage", "Radio Model": "DOT 4455", "Hardware Variant": "KRY 901 523/1", "Highest Frequency Band": "B66"})
                self.click(app, "Run RF calculations")
                result = app.session_state["mapl_result"]
                self.assertEqual(result["Dot_Model"], "DOT 4455")
                self.assertEqual(result["Band"], "B66")

    def test_saved_public_private_only_radio_is_invalidated(self):
        for filename in ("main.py", "simplified_ui.py"):
            with self.subTest(ui=filename):
                app = self.guided_intake(filename, *PRIVATE_CASES[2][:3], private=True)
                self.click(app, "Run RF calculations")
                app.session_state["rf_intake_data"] = dict(app.session_state["rf_intake_data"], Operator_type="Enterprise 5G Coverage")
                app.run()
                self.assert_app_ok(app)
                self.assertNotIn("dot_type", app.session_state["rf_intake_data"])
                self.assertIsNone(app.session_state["mapl_result"])
                self.assertIsNone(app.session_state["coverage_result_df"])
                options = next(widget for widget in app.selectbox if widget.label == "Radio Model").options
                self.assertFalse(any("4459" in option or "4479" in option for option in options))

    def test_private_micro_radio_uses_40_mhz(self):
        for filename in ("main.py", "simplified_ui.py"):
            with self.subTest(ui=filename):
                app = self.guided_intake(filename, "Micro Radio 4408", "B48", "KRC 161 746/1", private=True)
                self.click(app, "Run RF calculations")
                self.assertEqual(app.session_state["mapl_result"]["Bandwidth_MHz"], 40)
                self.assertEqual(app.session_state["mapl_result"]["RB_Count"], 106)

    def test_previous_private_bandwidth_result_is_cleared(self):
        for filename in ("main.py", "simplified_ui.py"):
            with self.subTest(ui=filename):
                app = self.guided_intake(filename, *PRIVATE_CASES[0][:3], private=True)
                self.click(app, "Run RF calculations")
                app.session_state["mapl_result"] = dict(app.session_state["mapl_result"], Bandwidth_MHz=80)
                app.run()
                self.assert_app_ok(app)
                self.assertIsNone(app.session_state["mapl_result"])
                self.assertIsNone(app.session_state["coverage_result_df"])
                self.click(app, "Run RF calculations")
                self.assertEqual(app.session_state["mapl_result"]["Bandwidth_MHz"], 40)


if __name__ == "__main__":
    unittest.main()
