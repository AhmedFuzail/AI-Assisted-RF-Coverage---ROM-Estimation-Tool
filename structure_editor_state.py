import math
from collections.abc import Mapping


def _area_percentage(value, fallback=0.0):
    try:
        percentage = float(value)
    except (TypeError, ValueError):
        percentage = float(fallback)
    if not math.isfinite(percentage):
        percentage = float(fallback)
    return min(max(percentage, 0.0), 100.0)


def reconcile_area_percentages(default_values, persisted_values=None):
    """Return one valid persisted percentage for every current structure row."""
    defaults = [_area_percentage(value) for value in default_values]
    persisted = list(persisted_values or [])
    return [
        _area_percentage(persisted[index], fallback=default_value)
        if index < len(persisted)
        else default_value
        for index, default_value in enumerate(defaults)
    ]


def apply_area_percentage_edits(current_values, editor_state):
    """Apply Streamlit data-editor percentage deltas to persistent values."""
    updated_values = list(current_values)
    if not isinstance(editor_state, Mapping):
        return updated_values

    edited_rows = editor_state.get("edited_rows", {})
    if not isinstance(edited_rows, Mapping):
        return updated_values

    for row_index, row_edits in edited_rows.items():
        if not isinstance(row_edits, Mapping) or "Sub_Type_Area_%" not in row_edits:
            continue
        try:
            index = int(row_index)
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(updated_values):
            updated_values[index] = _area_percentage(
                row_edits["Sub_Type_Area_%"],
                fallback=updated_values[index],
            )
    return updated_values
