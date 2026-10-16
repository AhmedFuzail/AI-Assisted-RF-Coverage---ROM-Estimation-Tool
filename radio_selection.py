"""Shared deployment and equipment filters for both Streamlit entry points."""

from radio_reference import (
    get_radio_dot_characteristics, get_radio_dot_models, get_radio_dot_variants,
    get_supported_bands,
)


ENTERPRISE_RADIO_BANDS = {
    "DOT 2274": {"B25", "B66"},
    "DOT 4455": {"B25", "B66", "B41", "B77D", "B77G"},
    "Micro Radio 4402": {"B25", "B66"},
    "Radio 4461HP": {"B40"},
    "Radio 2271": {"B28"},
}

PRIVATE_RADIO_BANDS = {
    "DOT 4459": {"B77S", "B48"},
    "DOT 4479": {"B78A", "B78L"},
    "Micro Radio 4408": {"B48"},
}

PRIVATE_RADIO_CHOICES = {
    "DOT 4459 : B77S": ("DOT 4459", "B77S"),
    "DOT 4479 : B78A": ("DOT 4479", "B78A"),
    "DOT 4479 : B78L": ("DOT 4479", "B78L"),
    "DOT 4459 : B48": ("DOT 4459", "B48"),
}


def synchronize_coverage_type(intake_data):
    """Private 5G uses NR; public coverage preserves the user's 4G/5G choice."""
    if intake_data.get("Operator_type") != "Enterprise Private 5G":
        return False
    changed = intake_data.get("Coverage_type") != "5G"
    intake_data["Coverage_type"] = "5G"
    return changed


def deployment_allowed_bands(intake_data):
    band_policy = (
        PRIVATE_RADIO_BANDS
        if intake_data.get("Operator_type") == "Enterprise Private 5G"
        else ENTERPRISE_RADIO_BANDS
    )
    model = intake_data.get("dot_type")
    if model:
        return set(band_policy.get(model, ()))
    return set().union(*band_policy.values())


def compatible_radio_models(intake_data, technology):
    equipment_type = intake_data.get("sol_type")
    prefix = {
        "DOT-IRU-BBU": "DOT ",
        "Micro-BBU": "Micro Radio ",
        "Radio-BBU": "Radio ",
    }.get(equipment_type, "DOT ")
    models = []
    for model in get_radio_dot_models():
        if not model.startswith(prefix):
            continue
        allowed = deployment_allowed_bands(dict(intake_data, dot_type=model))
        if allowed.intersection(get_supported_bands(model, technology=technology)):
            models.append(model)
    return models


def compatible_radio_choices(intake_data, technology):
    models = compatible_radio_models(intake_data, technology)
    if intake_data.get("Operator_type") != "Enterprise Private 5G":
        return models
    choices = [
        label for label, (model, band) in PRIVATE_RADIO_CHOICES.items()
        if model in models and band in get_supported_bands(model, technology=technology)
    ]
    return choices + [model for model in models if not model.startswith("DOT ")]


def selected_radio_choice(intake_data):
    model = intake_data.get("dot_type", "")
    band = intake_data.get("radio_model_band") or intake_data.get("Limit_freq_type")
    if intake_data.get("Operator_type") == "Enterprise Private 5G":
        for label, pair in PRIVATE_RADIO_CHOICES.items():
            if pair == (model, band):
                return label
    return model


def save_radio_choice(intake_data, choice):
    """Keep the RF lookup model canonical while retaining an explicit band choice."""
    model, band = PRIVATE_RADIO_CHOICES.get(choice, (choice, None))
    intake_data["dot_type"] = model
    for key in ("radio_model_band", "dot_variant_kry", "Limit_freq_type"):
        intake_data.pop(key, None)
    if band:
        intake_data["radio_model_band"] = band
        row = get_radio_dot_characteristics(model, None, band, "NR")
        intake_data["dot_variant_kry"] = row.dot_variant_kry
        intake_data["Limit_freq_type"] = band


def selection_allowed_bands(intake_data):
    allowed = deployment_allowed_bands(intake_data)
    selected_band = intake_data.get("radio_model_band")
    return allowed.intersection({selected_band}) if selected_band else allowed


def reconcile_radio_selection(intake_data, technology):
    """Clear incompatible dependencies after a deployment or technology change."""
    keys = ("dot_type", "radio_model_band", "dot_variant_kry", "Limit_freq_type")
    previous = {key: intake_data[key] for key in keys if key in intake_data}
    model = intake_data.get("dot_type")
    if model not in compatible_radio_models(intake_data, technology):
        for key in keys:
            intake_data.pop(key, None)
    else:
        allowed = deployment_allowed_bands(intake_data)
        if intake_data.get("radio_model_band") not in allowed:
            intake_data.pop("radio_model_band", None)
        allowed = selection_allowed_bands(intake_data)
        variants = [
            variant for variant in get_radio_dot_variants(model, technology)
            if allowed.intersection(get_supported_bands(model, variant, technology))
        ]
        if intake_data.get("dot_variant_kry") not in variants:
            intake_data.pop("dot_variant_kry", None)
            intake_data.pop("Limit_freq_type", None)
        if len(variants) == 1:
            intake_data["dot_variant_kry"] = variants[0]
        supported = get_supported_bands(model, intake_data.get("dot_variant_kry"), technology)
        if intake_data.get("Limit_freq_type") not in allowed.intersection(supported):
            intake_data.pop("Limit_freq_type", None)
    return previous != {key: intake_data[key] for key in keys if key in intake_data}
