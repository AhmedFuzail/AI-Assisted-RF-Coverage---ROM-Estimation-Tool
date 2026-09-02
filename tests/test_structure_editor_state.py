import unittest

from structure_editor_state import (
    apply_area_percentage_edits,
    reconcile_area_percentages,
)


class StructureEditorStateTests(unittest.TestCase):
    def test_reconcile_preserves_manual_values_and_adds_new_row_default(self):
        result = reconcile_area_percentages([40, 35, 25], [55, 45])

        self.assertEqual(result, [55.0, 45.0, 25.0])

    def test_apply_editor_delta_updates_only_the_changed_rows(self):
        result = apply_area_percentage_edits(
            [40.0, 35.0, 25.0],
            {"edited_rows": {"0": {"Sub_Type_Area_%": 50}, 1: {"Sub_Type_Area_%": 25}}},
        )

        self.assertEqual(result, [50.0, 25.0, 25.0])

    def test_invalid_editor_state_leaves_values_unchanged(self):
        self.assertEqual(apply_area_percentage_edits([60.0, 40.0], None), [60.0, 40.0])


if __name__ == "__main__":
    unittest.main()
