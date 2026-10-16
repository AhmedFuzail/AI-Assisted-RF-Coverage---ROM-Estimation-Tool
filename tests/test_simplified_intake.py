"""Exercise simplified intake choices through the real Streamlit state machine."""

import math
import os
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "simplified_ui.py"


class SimplifiedIntakeTests(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = Path.cwd()
        os.chdir(REPO_ROOT)
        self.addCleanup(os.chdir, self.previous_cwd)

    def assert_app_ok(self, app):
        self.assertEqual([error.message for error in app.exception], [])
        self.assertEqual([error.value for error in app.error], [])
        self.assertEqual([warning.value for warning in app.warning], [])

    def click(self, app, label):
        next(button for button in app.button if button.label == label).click().run()
        self.assert_app_ok(app)

    def guided_intake(self, *, private=False, micro=False, radio="DOT 4455", band="B77D", coverage="5G"):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        answers = {
            "Customer Name": "Intake regression test",
            "Venue Name": "Test office",
            "Total Sq.Ft Coverage": "100000",
            "General Building Type": "Office",
            "Building Category": "Open_Office",
            "Use Case Type": "Coverage Focused",
            "Equipment Type": "Micro-BBU" if micro else "DOT-IRU-BBU",
            "Operator Type": "Enterprise Private 5G" if private else "Enterprise 5G Coverage",
            "Coverage Type": coverage,
            "Radio Model": f"{radio} : {band}" if private and not micro else radio,
            "Hardware Variant": (
                "KRC 161 738/1" if micro else
                "KRY 901 551/1" if band in {"B41", "B77G"} else "KRY 901 523/1"
            ),
            "Highest Frequency Band": band,
        }
        for _ in range(20):
            self.assert_app_ok(app)
            if any(button.label == "Run RF calculations" for button in app.button):
                return app
            self.assertNotIn("Number of Floors", [widget.label for widget in app.text_input])
            self.assertNotIn("Operators on Highest Band", [widget.label for widget in app.select_slider])
            if private:
                self.assertNotIn("Coverage Type", [widget.label for widget in app.selectbox])
            for widget in app.text_input:
                if widget.label in answers:
                    widget.set_value(answers[widget.label])
            for widget in app.selectbox:
                if widget.label == "Equipment Type":
                    self.assertEqual(widget.options, ["Radio Dot Solution", "Micro Radio Solution", "Radio Solution"])
                if widget.label == "Radio Model" and not private and not micro:
                    expected = ["DOT 2274 : AWS/PCS", "DOT 4455 : C-band / B41"]
                    self.assertEqual(widget.options, expected)
                if widget.label in answers:
                    if widget.label == "Highest Frequency Band":
                        self.band_step = app.session_state["rf_intake_step"]
                    widget.select(answers[widget.label])
            self.click(app, "Save and continue")
        self.fail("The guided intake never completed")

    def assert_rf_operators(self, app, expected):
        self.click(app, "Run RF calculations")
        result = app.session_state["mapl_result"]
        self.assertEqual(result["Power_Share_Count"], expected)
        self.assertAlmostEqual(result["Carrier_Sharing_Loss_dB"], 10 * math.log10(expected))
        self.assertEqual(result["Power_Is_Total_Across_Carriers"], expected > 1)
        self.assertTrue(app.metric)
        return result

    def test_guided_dot_labels_summary_and_disabled_questions(self):
        app = self.guided_intake()
        result = self.assert_rf_operators(app, 2)
        self.assertEqual(result["Dot_Model"], "DOT 4455")
        self.assertEqual(result["Target_RSRP_dBm"], -100)
        self.assertEqual(app.session_state["rf_intake_data"]["sol_type"], "DOT-IRU-BBU")
        self.click(app, "Show/Hide Intake Summary")
        summary = "\n".join(element.value for element in app.markdown)
        self.assertIn("Radio Dot Solution", summary)
        self.assertIn("DOT 4455 : C-band / B41", summary)
        self.assertNotIn("DOT-IRU-BBU", summary)
        self.assertNotIn("Number of Floors", summary)
        self.assertIn("Operators on Highest Band", summary)
        self.click(app, "Modify intake")
        options = app.selectbox(key="rf_intake_edit_field").options
        self.assertIn("Equipment Type: Radio Dot Solution", options)
        self.assertIn("Radio Model: DOT 4455 : C-band / B41", options)
        self.assertIn("Coverage Type: 5G", options)
        self.assertFalse(any("Operators on Highest Band" in option or "Number of Floors" in option for option in options))

    def test_public_band_policy_replaces_saved_operator_count_and_cached_results(self):
        seed = self.guided_intake()
        # Use the completed intake's actual position so adding other questions
        # does not silently turn this calculation test into a partial intake.
        completed_step = seed.session_state["rf_intake_step"]
        original = dict(seed.session_state["rf_intake_data"])
        for band, variant, operators in [
            ("B77D", "KRY 901 523/1", 2),
            ("B41", "KRY 901 551/1", 2),
            ("B77G", "KRY 901 551/1", 2),
            ("B25", "KRY 901 523/1", 3),
            ("B66", "KRY 901 523/1", 3),
        ]:
            with self.subTest(band=band):
                app = AppTest.from_file(str(APP_PATH), default_timeout=30)
                intake = dict(original, Limit_freq_type=band, dot_variant_kry=variant, Operator_count=1)
                intake.pop("number_of_floors", None)
                app.session_state["rf_intake_data"] = intake
                app.session_state["rf_intake_step"] = completed_step
                app.session_state["mapl_result"] = {"outdated": True}
                app.session_state["coverage_result_df"] = "outdated"
                app.run()
                self.assert_app_ok(app)
                self.assertIsNone(app.session_state["mapl_result"])
                self.assertIsNone(app.session_state["coverage_result_df"])
                self.assertEqual(app.session_state["rf_intake_data"]["Operator_count"], operators)
                self.assert_rf_operators(app, operators)

    def test_band_edit_recomputes_operators_and_preserves_hardware_lookup(self):
        app = self.guided_intake()
        self.assert_rf_operators(app, 2)
        for band, expected in [("B66", 3), ("B77D", 2)]:
            self.click(app, "Modify intake")
            fields = app.selectbox(key="rf_intake_edit_field")
            fields.select(self.band_step).run()
            self.click(app, "Edit selected field")
            next(widget for widget in app.selectbox if widget.label == "Highest Frequency Band").select(band)
            self.click(app, "Save changes")
            self.assertIsNone(app.session_state["mapl_result"])
            result = self.assert_rf_operators(app, expected)
            self.assertEqual(result["Dot_Model"], "DOT 4455")
            self.assertEqual(result["Target_RSRP_dBm"], -100 if band == "B77D" else -95)

    def test_dot_2274_mapped_choice_reaches_calculation(self):
        app = self.guided_intake(radio="DOT 2274", band="B25")
        result = self.assert_rf_operators(app, 3)
        self.assertEqual(result["Dot_Model"], "DOT 2274")

    def test_micro_solution_reaches_calculation(self):
        app = self.guided_intake(micro=True, radio="Micro Radio 4402", band="B66")
        result = self.assert_rf_operators(app, 3)
        self.assertEqual(result["Dot_Model"], "Micro Radio 4402")
        self.assertEqual(app.session_state["rf_intake_data"]["sol_type"], "Micro-BBU")
        self.assertIn("Total required Micro Radios", [metric.label for metric in app.metric])

    def test_private_5g_keeps_single_operator(self):
        app = self.guided_intake(private=True, radio="DOT 4459", band="B48")
        result = self.assert_rf_operators(app, 1)
        self.assertEqual(result["Dot_Model"], "DOT 4459")
        self.assertEqual(result["Target_RSRP_dBm"], -95)

    def test_lte_b41_uses_two_operators(self):
        app = self.guided_intake(band="B41", coverage="4G")
        result = self.assert_rf_operators(app, 2)
        self.assertEqual(result["Technology"], "LTE")

    def test_b41k_is_not_treated_as_b41(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30)
        app.session_state["rf_intake_data"] = {
            "Operator_type": "Enterprise 5G Coverage", "Limit_freq_type": "B41K", "Operator_count": 2,
        }
        app.run()
        self.assert_app_ok(app)
        self.assertEqual(app.session_state["rf_intake_data"]["Operator_count"], 3)


if __name__ == "__main__":
    unittest.main()
