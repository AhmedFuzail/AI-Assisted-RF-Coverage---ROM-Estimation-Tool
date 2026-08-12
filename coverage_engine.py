import math
from collections.abc import Mapping

import pandas as pd


SQFT_PER_M2 = 10.7639104167
STREAMLIT_DESIGN_MARGIN_DB = 14.0

BAND_CENTER_FREQUENCY_MHZ = {
    "B48-CBRS": 3625.0,
    "B2/B25": 1962.5,
    "B4/B66": 2155.0,
    "N77/C-Band": 3750.0,
}

ITU_COEFFICIENTS = {
    "office": {
        "los": {"alpha": 1.47, "beta": 34.17, "gamma": 2.08, "sigma_db": 3.68, "frequency_ghz": (0.3, 294.0), "distance_m": (2.0, 27.0)},
        "nlos": {"alpha": 2.39, "beta": 30.13, "gamma": 2.40, "sigma_db": 5.01, "frequency_ghz": (0.3, 255.0), "distance_m": (4.0, 30.0)},
    },
    "corridor": {
        "los": {"alpha": 1.57, "beta": 29.46, "gamma": 2.24, "sigma_db": 3.77, "frequency_ghz": (0.3, 300.0), "distance_m": (2.0, 160.0)},
        "nlos": {"alpha": 2.78, "beta": 28.62, "gamma": 2.54, "sigma_db": 7.58, "frequency_ghz": (0.625, 159.0), "distance_m": (3.0, 94.0)},
    },
    "industrial": {
        "los": {"alpha": 2.27, "beta": 24.79, "gamma": 2.10, "sigma_db": 2.62, "frequency_ghz": (0.625, 294.0), "distance_m": (2.0, 102.0)},
        "nlos": {"alpha": 2.80, "beta": 23.55, "gamma": 2.16, "sigma_db": 5.70, "frequency_ghz": (0.625, 255.0), "distance_m": (3.0, 110.0)},
    },
    "conference": {
        "los": {"alpha": 1.56, "beta": 30.47, "gamma": 2.23, "sigma_db": 2.92, "frequency_ghz": (0.45, 300.0), "distance_m": (2.0, 21.0)},
        "nlos": {"alpha": 1.40, "beta": 39.53, "gamma": 2.37, "sigma_db": 3.33, "frequency_ghz": (0.45, 159.0), "distance_m": (4.0, 25.0)},
    },
}

PROFILE_ENVIRONMENT_MAP = {
    "Admin_Office": "office",
    "Airport_Public": "corridor",
    "Baggage_Industrial": "industrial",
    "Bathroom": "office",
    "Book_Stacks": "corridor",
    "Breakroom": "office",
    "Bulk_Racking": "industrial",
    "Cleanroom": "industrial",
    "Cleanroom_Support": "industrial",
    "Concourse_Public": "corridor",
    "Corridor": "corridor",
    "Data_Center": "industrial",
    "Education_Classroom": "conference",
    "Food_Court_Dining": "conference",
    "Gowning": "industrial",
    "Grocery": "corridor",
    "Gym_Auditorium": "conference",
    "Healthcare_Clinic": "office",
    "Healthcare_Emergency": "office",
    "Healthcare_Imaging": "office",
    "Healthcare_OR_ICU": "office",
    "Healthcare_Patient": "office",
    "Heavy_Production": "industrial",
    "Hotel_Guestroom": "office",
    "IT_MEP": "industrial",
    "Kitchen_Service": "industrial",
    "Lab": "industrial",
    "Library": "conference",
    "Light_Assembly": "industrial",
    "Lobby_Public": "office",
    "Meeting": "conference",
    "Museum_Gallery": "conference",
    "Office_Dense": "office",
    "Office_Open": "office",
    "Office_Private": "office",
    "Parking": "industrial",
    "Port_Cargo": "industrial",
    "Power_Cooling": "industrial",
    "Public_Seating": "conference",
    "Residential_Living": "office",
    "Retail_Sales": "office",
    "Secure_Government": "office",
    "Security_Screening": "corridor",
    "Storage": "industrial",
    "Warehouse": "industrial",
    "Workshop": "industrial",
    "Worship_Hall": "conference",
}

APPROXIMATE_PROFILES = {
    "Airport_Public", "Bathroom", "Book_Stacks", "Food_Court_Dining", "Grocery",
    "Healthcare_Clinic", "Healthcare_Emergency", "Healthcare_Imaging",
    "Healthcare_OR_ICU", "Healthcare_Patient", "Hotel_Guestroom", "Library",
    "Lobby_Public", "Museum_Gallery", "Parking", "Public_Seating",
    "Residential_Living", "Retail_Sales", "Security_Screening", "Worship_Hall",
}

ENVIRONMENT_TYPE_MAP = {
    "Indoor_Cleanroom": ("industrial", "Medium"),
    "Indoor_Conditioned": ("office", "Medium"),
    "Indoor_Data_Center": ("industrial", "Medium"),
    "Indoor_Education": ("conference", "Medium"),
    "Indoor_Healthcare": ("office", "Low"),
    "Indoor_Hospitality": ("office", "Low"),
    "Indoor_Industrial": ("industrial", "High"),
    "Indoor_Lab": ("industrial", "Medium"),
    "Indoor_Public_Venue": ("conference", "Medium"),
    "Indoor_Residential": ("office", "Low"),
    "Indoor_Retail": ("office", "Low"),
    "Indoor_Transportation": ("corridor", "Low"),
    "Outdoor_Covered": ("industrial", "Low"),
}

BUILDING_TYPE_MAP = {
    "Data_Center": ("industrial", "Medium"),
    "Education": ("conference", "Low"),
    "Healthcare": ("office", "Low"),
    "Hospitality": ("office", "Low"),
    "Industrial": ("industrial", "Medium"),
    "Office": ("office", "Medium"),
    "Public_Venue": ("conference", "Low"),
    "Residential": ("office", "Low"),
    "Retail": ("office", "Low"),
    "Transportation": ("corridor", "Low"),
}

FIELD_ALIASES = {
    "Area_ID": ("Area_ID", "area_id", "Building_ID", "building_id", "Row_ID", "row_id"),
    "Building_Name": ("Building_Name", "building_name", "venue_name", "Venue Name"),
    "Building_Type": ("Building_Type", "Building_type", "building_type"),
    "Category": ("Category", "Building_category", "building_category"),
    "Sub_Type_A": ("Sub_Type_A", "Sub_Type", "sub_type", "subtype"),
    "Coverage Area": ("Coverage Area", "Coverage_Area", "coverage_area_sqft"),
    "Assumption_Profile": ("Assumption_Profile", "assumption_profile"),
    "Environment_Type": ("Environment_Type", "environment_type"),
    "Layout_Complexity": ("Layout_Complexity", "layout_complexity"),
    "Ceiling_Height_Class": ("Ceiling_Height_Class", "ceiling_height_class"),
    "Mobility_Pattern": ("Mobility_Pattern", "mobility_pattern"),
    "Concrete_%": ("Concrete_%", "concrete_pct"),
    "Drywall_%": ("Drywall_%", "drywall_pct"),
    "Glass_%": ("Glass_%", "glass_pct"),
    "Metal_%": ("Metal_%", "metal_pct"),
    "Open_Area_%": ("Open_Area_%", "open_area_pct"),
    "Light_Clutter_%": ("Light_Clutter_%", "light_clutter_pct"),
    "Medium_Clutter_%": ("Medium_Clutter_%", "medium_clutter_pct"),
    "Dense_Clutter_%": ("Dense_Clutter_%", "dense_clutter_pct"),
    "Total Losses Material": ("Total Losses Material", "Total_Losses_Material", "material_loss_db"),
    "Total Loss Density": ("Total Loss Density", "Total_Loss_Density", "clutter_loss_db"),
    "Total Loss": ("Total Loss", "Total_Loss", "total_loss_db"),
    "Band": ("Band", "band", "frequency_band", "Limit_freq_type", "limiting_band"),
    "Frequency_MHz": ("Frequency_MHz", "frequency_mhz", "center_frequency_mhz", "operating_frequency_mhz"),
}

RESULT_COLUMNS = [
    "Area_ID", "Building_Name", "Building_Type", "Category", "Sub_Type",
    "Area_Coverage_sqft", "Coverage_Type", "Technology", "Band",
    "Dot_Model", "Dot_Variant_KRY", "Duplex_Mode", "Tx_Branch_Count",
    "Effective_Tx_Power_dBm_per_Branch", "Antenna_Gain_dBi", "Branch_EIRP_dBm",
    "Radio_Data_Source", "Frequency_MHz", "Frequency_Source", "Bandwidth_MHz", "SCS_kHz", "RB_Count",
    "MAPL_Before_Margin_dB", "Margin_dB", "Additional_Loss_dB", "Usable_MAPL_dB",
    "ITU_Environment", "ITU_Condition", "Environment_Mapping_Reason", "Condition_Reason",
    "Alpha", "Beta", "Gamma", "Sigma_dB", "Coverage_Radius_m", "Coverage_Diameter_m",
    "Planning_Coverage_Radius_m", "Coverage_Capped_To_Model_Range",
    "Ideal_Area_m2", "Ideal_Area_sqft", "Area_Efficiency", "Planning_Area_m2",
    "Planning_Area_sqft", "Number_of_required_DOTs_Radios",
    "Environment_Mapping_Confidence", "Condition_Confidence",
    "Loss_Calculation_Source", "Frequency_Range_Valid", "Distance_Range_Valid",
    "Is_Limiting_Band", "Calculation_Status", "Result_Valid_For_Planning",
    "Override_Fields", "Warnings",
]


def _normalized_key(value):
    return "".join(character.lower() for character in str(value) if character.isalnum())


def _as_dict(record):
    if isinstance(record, pd.Series):
        return record.to_dict()
    if isinstance(record, Mapping):
        return dict(record)
    raise TypeError("record must be a dict, mapping, or pandas.Series.")


def _to_float(value, field_name, allow_none=False):
    if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).strip() == "":
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required.")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be numeric.") from error


def _deduplicate_warnings(warnings):
    return list(dict.fromkeys(str(warning) for warning in warnings if warning))


def normalize_building_record(record):
    source = _as_dict(record)
    source_lookup = {_normalized_key(key): value for key, value in source.items()}
    normalized = dict(source)
    for canonical_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            alias_key = _normalized_key(alias)
            if alias_key in source_lookup:
                normalized[canonical_name] = source_lookup[alias_key]
                break
    return normalized


def resolve_technology(operator_type, coverage_type=None):
    operator = str(operator_type or "").strip().lower()
    coverage = str(coverage_type or "").strip().upper()
    if operator == "enterprise private 5g":
        return "NR"
    if operator == "enterprise 5g coverage":
        if coverage == "4G":
            return "LTE"
        if coverage == "5G":
            return "NR"
        raise ValueError("Coverage Type must be 4G or 5G for Enterprise 5G Coverage.")
    if coverage == "4G" or operator in {"lte", "4g"}:
        return "LTE"
    if coverage == "5G" or operator in {"nr", "5g", "5g nr"}:
        return "NR"
    raise ValueError("Unable to determine LTE or NR technology.")


def resolve_radio_power_mw(radio_type, band):
    normalized_radio = _normalized_key(radio_type).upper()
    if normalized_radio in {"RD4455", "DOT4455"} and str(band).strip() != "N77/C-Band":
        return 200.0
    return 400.0


def resolve_frequency_mhz(record, technology=None):
    normalized = normalize_building_record(record)
    warnings = []
    exact_frequency = normalized.get("Frequency_MHz")
    if exact_frequency is not None and str(exact_frequency).strip() != "":
        frequency_mhz = _to_float(exact_frequency, "frequency_mhz")
        if frequency_mhz <= 0:
            raise ValueError("frequency_mhz must be greater than 0.")
        return {
            "frequency_mhz": frequency_mhz,
            "band": str(normalized.get("Band", "")).strip(),
            "source": "exact_configured_frequency",
            "warnings": warnings,
        }

    band = str(normalized.get("Band", "")).strip()
    if band not in BAND_CENTER_FREQUENCY_MHZ:
        raise ValueError(f"No center-frequency mapping exists for band: {band or 'missing'}.")
    warnings.append(f"Frequency resolved from the {band} center-frequency lookup.")
    return {
        "frequency_mhz": BAND_CENTER_FREQUENCY_MHZ[band],
        "band": band,
        "source": "band_center_lookup",
        "warnings": warnings,
    }


def map_building_to_itu_environment(record):
    normalized = normalize_building_record(record)
    warnings = []
    profile = str(normalized.get("Assumption_Profile", "")).strip()
    if profile in PROFILE_ENVIRONMENT_MAP:
        environment = PROFILE_ENVIRONMENT_MAP[profile]
        confidence = "Medium" if profile in APPROXIMATE_PROFILES else "High"
        reason = f"Assumption_Profile {profile} mapped to {environment}."
        if confidence != "High":
            warnings.append(f"The {profile} to {environment} ITU mapping is approximate.")
        return {"environment": environment, "reason": reason, "confidence": confidence, "warnings": warnings}

    subtype = str(normalized.get("Sub_Type_A", "")).strip().lower()
    keyword_rules = (
        ("corridor", ("corridor", "concourse", "aisle", "circulation")),
        ("conference", ("conference", "meeting", "classroom", "lecture", "auditorium", "sanctuary")),
        ("industrial", ("warehouse", "production", "storage", "mechanical", "utility", "server", "rack", "lab", "workshop", "baggage", "cargo")),
        ("office", ("office", "admin", "guestroom", "patient", "clinic", "lobby", "reception")),
    )
    for environment, keywords in keyword_rules:
        matched_keyword = next((keyword for keyword in keywords if keyword in subtype), None)
        if matched_keyword:
            warnings.append("ITU environment selected from subtype keywords because no mapped assumption profile was available.")
            return {
                "environment": environment,
                "reason": f"Sub_Type_A contains '{matched_keyword}'.",
                "confidence": "Medium",
                "warnings": warnings,
            }

    environment_type = str(normalized.get("Environment_Type", "")).strip()
    if environment_type in ENVIRONMENT_TYPE_MAP:
        environment, confidence = ENVIRONMENT_TYPE_MAP[environment_type]
        warnings.append(f"The {environment_type} to {environment} ITU mapping is a fallback approximation.")
        if environment_type == "Outdoor_Covered":
            warnings.append("ITU-R P.1238 is an indoor model; Outdoor_Covered is outside its intended environment.")
        return {
            "environment": environment,
            "reason": f"Environment_Type {environment_type} mapped to {environment}.",
            "confidence": confidence,
            "warnings": warnings,
        }

    building_type = str(normalized.get("Building_Type", "")).strip()
    if building_type in BUILDING_TYPE_MAP:
        environment, confidence = BUILDING_TYPE_MAP[building_type]
        warnings.append(f"ITU environment defaulted from Building_Type {building_type}.")
        return {
            "environment": environment,
            "reason": f"Building_Type fallback mapped {building_type} to {environment}.",
            "confidence": confidence,
            "warnings": warnings,
        }

    warnings.append("No supported building environment was found; office NLOS assumptions are the conservative fallback.")
    return {
        "environment": "office",
        "reason": "Default office environment used because building environment data was missing.",
        "confidence": "Low",
        "warnings": warnings,
    }


def _read_percentage_group(record, field_names, group_name):
    normalized = normalize_building_record(record)
    values = {}
    warnings = []
    for field_name in field_names:
        value = _to_float(normalized.get(field_name), field_name, allow_none=True)
        if value is None:
            warnings.append(f"Missing {group_name} percentage: {field_name}.")
            return None, warnings
        if value < 0 or value > 100:
            warnings.append(f"{field_name} must be between 0 and 100.")
            return None, warnings
        values[field_name] = value
    total = sum(values.values())
    if total <= 0:
        warnings.append(f"{group_name.capitalize()} percentages total zero.")
        return None, warnings
    if abs(total - 100.0) > 1.0:
        warnings.append(f"{group_name.capitalize()} percentages total {total:.1f}% instead of 100%.")
        return None, warnings
    if abs(total - 100.0) > 0.01:
        warnings.append(f"{group_name.capitalize()} percentages total {total:.1f}% and were normalized for calculation.")
    return values, warnings


def classify_los_nlos(record):
    normalized = normalize_building_record(record)
    fields = ("Open_Area_%", "Light_Clutter_%", "Medium_Clutter_%", "Dense_Clutter_%")
    clutter, warnings = _read_percentage_group(normalized, fields, "clutter")
    if clutter is None:
        warnings.append("NLOS was selected as the conservative default because clutter data is incomplete or invalid.")
        return {"condition": "nlos", "reason": "Conservative fallback for incomplete clutter data.", "confidence": "Low", "warnings": warnings}

    open_pct = clutter["Open_Area_%"]
    medium_pct = clutter["Medium_Clutter_%"]
    dense_pct = clutter["Dense_Clutter_%"]
    layout = str(normalized.get("Layout_Complexity", "")).strip().lower().replace("_", " ")
    profile = str(normalized.get("Assumption_Profile", "")).strip()

    if profile == "Corridor" and layout == "simple" and open_pct >= 40 and dense_pct <= 10:
        return {"condition": "los", "reason": "Simple corridor with high openness and low dense clutter.", "confidence": "High", "warnings": warnings}

    los_checks = (
        open_pct >= 55,
        dense_pct <= 10,
        medium_pct + dense_pct <= 25,
        layout in {"simple", "moderate"},
    )
    if all(los_checks):
        return {"condition": "los", "reason": "High open area, low obstructive clutter, and simple/moderate layout.", "confidence": "High", "warnings": warnings}

    nlos_reasons = []
    if layout == "very complex":
        nlos_reasons.append("very complex layout")
    if dense_pct >= 25:
        nlos_reasons.append("dense clutter at or above 25%")
    if medium_pct + dense_pct >= 45:
        nlos_reasons.append("medium plus dense clutter at or above 45%")
    if open_pct <= 20:
        nlos_reasons.append("open area at or below 20%")
    if nlos_reasons:
        confidence = "High" if len(nlos_reasons) >= 2 else "Medium"
        return {"condition": "nlos", "reason": ", ".join(nlos_reasons).capitalize() + ".", "confidence": confidence, "warnings": warnings}

    warnings.append("LOS/NLOS indicators were mixed; NLOS was selected conservatively.")
    return {"condition": "nlos", "reason": "Mixed obstruction indicators; conservative NLOS selection.", "confidence": "Medium", "warnings": warnings}


def calculate_incremental_loss_db(record, override_db=None):
    normalized = normalize_building_record(record)
    if override_db is not None and not (isinstance(override_db, float) and math.isnan(override_db)):
        value = _to_float(override_db, "additional_loss_db")
        if value < 0:
            raise ValueError("additional_loss_db must be non-negative.")
        return {"additional_loss_db": value, "source": "manual_incremental_override", "warnings": []}

    loss_fields = ("Total Loss", "Total Losses Material", "Total Loss Density")
    present_fields = [field for field in loss_fields if normalized.get(field) is not None and str(normalized.get(field)).strip() != ""]
    warnings = []
    if present_fields:
        warnings.append("Workbook material/clutter losses were retained as diagnostics and not subtracted from the ITU site-general model to avoid double-counting.")
    else:
        warnings.append("No calibrated incremental loss was available; additional loss defaulted to 0 dB.")
    return {"additional_loss_db": 0.0, "source": "itu_coefficients_only", "warnings": warnings}


def calculate_area_efficiency(record, override=None):
    normalized = normalize_building_record(record)
    if override is not None and not (isinstance(override, float) and math.isnan(override)):
        value = _to_float(override, "area_efficiency")
        if value < 0.30 or value > 1.00:
            raise ValueError("area_efficiency must be between 0.30 and 1.00.")
        return {"area_efficiency": value, "source": "manual_override", "warnings": []}

    layout = str(normalized.get("Layout_Complexity", "")).strip().lower().replace("_", " ")
    layout_multipliers = {"simple": 1.00, "moderate": 0.90, "complex": 0.75, "very complex": 0.60}
    layout_defaults = {"simple": 0.85, "moderate": 0.70, "complex": 0.50, "very complex": 0.35}
    layout_multiplier = layout_multipliers.get(layout)
    warnings = []
    if layout_multiplier is None:
        layout_multiplier = 0.75
        warnings.append("Layout complexity was missing or unsupported; the Complex multiplier was used.")

    fields = ("Open_Area_%", "Light_Clutter_%", "Medium_Clutter_%", "Dense_Clutter_%")
    clutter, clutter_warnings = _read_percentage_group(normalized, fields, "clutter")
    warnings.extend(clutter_warnings)
    if clutter is None:
        default_value = layout_defaults.get(layout, 0.50)
        warnings.append(f"Area efficiency defaulted to {default_value:.2f} from layout complexity.")
        return {"area_efficiency": default_value, "source": "layout_default", "warnings": warnings}

    total = sum(clutter.values())
    clutter_shape = (
        1.0 * clutter["Open_Area_%"]
        + 0.8 * clutter["Light_Clutter_%"]
        + 0.6 * clutter["Medium_Clutter_%"]
        + 0.3 * clutter["Dense_Clutter_%"]
    ) / total
    efficiency = min(1.00, max(0.30, clutter_shape * layout_multiplier))
    return {"area_efficiency": efficiency, "source": "clutter_layout_formula", "warnings": warnings}


def normalize_mapl_result(mapl_result):
    if isinstance(mapl_result, pd.DataFrame):
        if {"Parameter", "Value"}.issubset(mapl_result.columns):
            source = dict(zip(mapl_result["Parameter"], mapl_result["Value"]))
        elif len(mapl_result) == 1:
            source = mapl_result.iloc[0].to_dict()
        else:
            raise ValueError("A multi-row MAPL DataFrame must be passed to the batch function.")
    else:
        source = _as_dict(mapl_result)

    lookup = {_normalized_key(key): value for key, value in source.items()}

    def pick(*names, required=False):
        for name in names:
            key = _normalized_key(name)
            if key in lookup and lookup[key] is not None and str(lookup[key]).strip() != "":
                return lookup[key]
        if required:
            raise ValueError(f"Missing MAPL value: {names[0]}.")
        return None

    technology = str(pick("Technology", required=True)).strip().upper()
    if technology in {"4G"}:
        technology = "LTE"
    if technology in {"5G", "5G NR"}:
        technology = "NR"
    if technology not in {"LTE", "NR"}:
        raise ValueError(f"Unsupported technology: {technology}.")

    return {
        "Technology": technology,
        "Band": str(pick("Band") or "").strip(),
        "Frequency_MHz": _to_float(pick("Frequency_MHz", "Resolved Center Frequency"), "Frequency_MHz", allow_none=True),
        "Frequency_Source": str(pick("Frequency_Source") or "").strip(),
        "Bandwidth_MHz": _to_float(pick("Bandwidth_MHz", "Bandwidth"), "Bandwidth_MHz", allow_none=True),
        "SCS_kHz": _to_float(pick("SCS_kHz", "SCS"), "SCS_kHz", allow_none=True),
        "RB_Count": _to_float(pick("RB_Count", "RB Count"), "RB_Count", allow_none=True),
        "MAPL_Before_Margin_dB": _to_float(pick("MAPL_Before_Margin_dB", "MAPL Before Margin", required=True), "MAPL_Before_Margin_dB"),
        "Dot_Model": str(pick("Dot_Model", "dot_model") or "").strip(),
        "Dot_Variant_KRY": str(pick("Dot_Variant_KRY", "dot_variant_kry") or "").strip(),
        "Duplex_Mode": str(pick("Duplex_Mode", "duplex_mode") or "").strip(),
        "Tx_Branch_Count": _to_float(pick("Tx_Branch_Count", "tx_branch_count"), "Tx_Branch_Count", allow_none=True),
        "Effective_Tx_Power_dBm_per_Branch": _to_float(
            pick("Effective_Tx_Power_dBm_per_Branch", "effective_tx_power_dbm_per_branch"),
            "Effective_Tx_Power_dBm_per_Branch",
            allow_none=True,
        ),
        "Antenna_Gain_dBi": _to_float(pick("Antenna_Gain_dBi", "antenna_gain_dbi"), "Antenna_Gain_dBi", allow_none=True),
        "Branch_EIRP_dBm": _to_float(pick("Branch_EIRP_dBm", "branch_eirp_dbm"), "Branch_EIRP_dBm", allow_none=True),
        "Radio_Data_Source": str(pick("Data_Source", "Radio_Data_Source", "data_source") or "").strip(),
        "Override_Fields": str(pick("Override_Fields", "override_fields") or "").strip(),
        "Warnings": str(pick("Warnings", "warnings") or "").strip(),
    }


def convert_mapl_to_coverage(
    mapl_before_margin_db,
    frequency_mhz,
    environment,
    condition,
    margin_db=6.0,
    additional_loss_db=0.0,
    area_efficiency=1.0,
    custom_coefficients=None,
):
    mapl = _to_float(mapl_before_margin_db, "mapl_before_margin_db")
    frequency = _to_float(frequency_mhz, "frequency_mhz")
    margin = _to_float(margin_db, "margin_db")
    additional_loss = _to_float(additional_loss_db, "additional_loss_db")
    efficiency = _to_float(area_efficiency, "area_efficiency")
    if mapl <= 0:
        raise ValueError("mapl_before_margin_db must be greater than 0.")
    if frequency <= 0:
        raise ValueError("frequency_mhz must be greater than 0.")
    if margin < 0:
        raise ValueError("margin_db must be non-negative.")
    if additional_loss < 0:
        raise ValueError("additional_loss_db must be non-negative.")
    if efficiency < 0.30 or efficiency > 1.00:
        raise ValueError("area_efficiency must be between 0.30 and 1.00.")

    environment_key = str(environment).strip().lower().replace("/lecture room", "").replace(" room", "")
    condition_key = str(condition).strip().lower()
    if custom_coefficients is None:
        if environment_key not in ITU_COEFFICIENTS or condition_key not in ITU_COEFFICIENTS[environment_key]:
            raise ValueError(f"No ITU coefficient set exists for {environment}/{condition}.")
        coefficients = ITU_COEFFICIENTS[environment_key][condition_key]
    else:
        coefficients = dict(custom_coefficients)
        required_keys = {"alpha", "beta", "gamma", "sigma_db", "frequency_ghz", "distance_m"}
        if not required_keys.issubset(coefficients):
            raise ValueError("custom_coefficients is missing required values.")

    usable_mapl = mapl - margin - additional_loss
    if usable_mapl <= 0:
        raise ValueError("Usable MAPL must be greater than 0 dB.")
    frequency_ghz = frequency / 1000.0
    exponent = (
        usable_mapl
        - coefficients["beta"]
        - 10.0 * coefficients["gamma"] * math.log10(frequency_ghz)
    ) / (10.0 * coefficients["alpha"])
    try:
        radius_m = 10.0 ** exponent
    except OverflowError as error:
        raise ValueError("Calculated coverage radius overflowed; review MAPL and coefficient inputs.") from error
    if not math.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("Calculated coverage radius is nonphysical.")

    frequency_range = coefficients["frequency_ghz"]
    distance_range = coefficients["distance_m"]
    frequency_valid = frequency_range[0] <= frequency_ghz <= frequency_range[1]
    distance_valid = distance_range[0] <= radius_m <= distance_range[1]
    planning_radius_m = radius_m
    coverage_capped = False
    warnings = []
    if not frequency_valid:
        warnings.append(f"Frequency {frequency_ghz:.3f} GHz is outside the ITU model range {frequency_range[0]}-{frequency_range[1]} GHz.")
    if radius_m > distance_range[1]:
        planning_radius_m = float(distance_range[1])
        coverage_capped = True
        warnings.append(
            f"Calculated radius {radius_m:.2f} m exceeds the ITU model range; "
            f"planning coverage was capped at {planning_radius_m:.2f} m."
        )
    elif radius_m < distance_range[0]:
        warnings.append(f"Calculated radius {radius_m:.2f} m is outside the ITU model range {distance_range[0]}-{distance_range[1]} m.")
    ideal_area_m2 = math.pi * radius_m ** 2
    planning_area_m2 = math.pi * planning_radius_m ** 2 * efficiency
    if radius_m > 1000 or planning_area_m2 * SQFT_PER_M2 > 10_000_000:
        warnings.append("Calculated coverage is extreme and should not be used for planning without calibration.")

    return {
        "Usable_MAPL_dB": usable_mapl,
        "Alpha": coefficients["alpha"],
        "Beta": coefficients["beta"],
        "Gamma": coefficients["gamma"],
        "Sigma_dB": coefficients["sigma_db"],
        "Coverage_Radius_m": radius_m,
        "Coverage_Diameter_m": radius_m * 2.0,
        "Planning_Coverage_Radius_m": planning_radius_m,
        "Coverage_Capped_To_Model_Range": coverage_capped,
        "Ideal_Area_m2": ideal_area_m2,
        "Ideal_Area_sqft": ideal_area_m2 * SQFT_PER_M2,
        "Planning_Area_m2": planning_area_m2,
        "Planning_Area_sqft": planning_area_m2 * SQFT_PER_M2,
        "Frequency_Range_Valid": frequency_valid,
        "Distance_Range_Valid": distance_valid,
        "Calculation_Status": "ok" if frequency_valid and distance_valid else "warning_extrapolated",
        "warnings": warnings,
    }


def calculate_building_coverage(record, mapl_result, margin_db=6.0, overrides=None):
    normalized = normalize_building_record(record)
    mapl = normalize_mapl_result(mapl_result)
    overrides = dict(overrides or {})
    warnings = [
        warning.strip()
        for warning in str(mapl.get("Warnings", "")).split(";")
        if warning.strip()
    ]

    frequency_input = dict(normalized)
    frequency_input["Band"] = mapl.get("Band") or normalized.get("Band")
    if mapl.get("Frequency_MHz") is not None:
        frequency_input["Frequency_MHz"] = mapl["Frequency_MHz"]
    frequency = resolve_frequency_mhz(frequency_input, mapl["Technology"])
    if mapl.get("Frequency_Source"):
        frequency["source"] = mapl["Frequency_Source"]
        if mapl["Frequency_Source"] == "band_center_lookup":
            frequency["warnings"].append(f"Frequency resolved from the {frequency['band']} center-frequency lookup.")
    warnings.extend(frequency["warnings"])

    environment_mapping = map_building_to_itu_environment(normalized)
    warnings.extend(environment_mapping["warnings"])
    environment = environment_mapping["environment"]
    environment_reason = environment_mapping["reason"]
    environment_confidence = environment_mapping["confidence"]
    override_fields = [
        field.strip()
        for field in str(mapl.get("Override_Fields", "")).split(",")
        if field.strip()
    ]
    environment_override = overrides.get("environment")
    if environment_override:
        environment = str(environment_override).strip().lower()
        environment_reason = "Manual ITU environment override."
        environment_confidence = "Manual Override"
        override_fields.append("ITU_Environment")

    condition_mapping = classify_los_nlos(normalized)
    warnings.extend(condition_mapping["warnings"])
    condition = condition_mapping["condition"]
    condition_reason = condition_mapping["reason"]
    condition_confidence = condition_mapping["confidence"]
    condition_override = overrides.get("condition")
    if condition_override:
        condition = str(condition_override).strip().lower()
        condition_reason = "Manual LOS/NLOS override."
        condition_confidence = "Manual Override"
        override_fields.append("ITU_Condition")

    loss = calculate_incremental_loss_db(normalized, overrides.get("additional_loss_db"))
    warnings.extend(loss["warnings"])
    if overrides.get("additional_loss_db") is not None:
        override_fields.append("Additional_Loss_dB")

    efficiency = calculate_area_efficiency(normalized, overrides.get("area_efficiency"))
    warnings.extend(efficiency["warnings"])
    if overrides.get("area_efficiency") is not None:
        override_fields.append("Area_Efficiency")

    material_fields = ("Concrete_%", "Drywall_%", "Glass_%", "Metal_%")
    _, material_warnings = _read_percentage_group(normalized, material_fields, "material")
    warnings.extend(material_warnings)
    ceiling_class = str(normalized.get("Ceiling_Height_Class", "")).strip()
    if ceiling_class in {"High_18_30ft", "Very_High_30ft_plus"}:
        warnings.append("High ceiling is informational in v1; ITU 3D distance is used as the planning-radius approximation.")

    coverage = convert_mapl_to_coverage(
        mapl_before_margin_db=mapl["MAPL_Before_Margin_dB"],
        frequency_mhz=frequency["frequency_mhz"],
        environment=environment,
        condition=condition,
        margin_db=margin_db,
        additional_loss_db=loss["additional_loss_db"],
        area_efficiency=efficiency["area_efficiency"],
    )
    warnings.extend(coverage.pop("warnings"))
    area_coverage_sqft = _to_float(
        normalized.get("Coverage Area"),
        "Coverage Area",
        allow_none=True,
    )
    required_radios = None
    planning_area_sqft = coverage.get("Planning_Area_sqft")
    if area_coverage_sqft is None:
        warnings.append("Area coverage is missing; required radio count could not be calculated.")
    elif area_coverage_sqft < 0:
        warnings.append("Area coverage cannot be negative; required radio count was not calculated.")
    elif area_coverage_sqft == 0:
        required_radios = 0
    elif planning_area_sqft is None or not math.isfinite(float(planning_area_sqft)) or float(planning_area_sqft) <= 0:
        warnings.append("Planning coverage per radio is unavailable or nonpositive; required radio count could not be calculated.")
    else:
        required_radios = math.ceil(area_coverage_sqft / float(planning_area_sqft))
    warnings = _deduplicate_warnings(warnings)

    technology = mapl["Technology"]
    result = {
        "Area_ID": str(normalized.get("Area_ID", "")).strip(),
        "Building_Name": str(normalized.get("Building_Name", "")).strip(),
        "Building_Type": str(normalized.get("Building_Type", "")).strip(),
        "Category": str(normalized.get("Category", "")).strip(),
        "Sub_Type": str(normalized.get("Sub_Type_A", "")).strip(),
        "Area_Coverage_sqft": area_coverage_sqft,
        "Coverage_Type": "lte_coverage" if technology == "LTE" else "nr_coverage",
        "Technology": technology,
        "Band": frequency["band"],
        "Dot_Model": mapl["Dot_Model"],
        "Dot_Variant_KRY": mapl["Dot_Variant_KRY"],
        "Duplex_Mode": mapl["Duplex_Mode"],
        "Tx_Branch_Count": mapl["Tx_Branch_Count"],
        "Effective_Tx_Power_dBm_per_Branch": mapl["Effective_Tx_Power_dBm_per_Branch"],
        "Antenna_Gain_dBi": mapl["Antenna_Gain_dBi"],
        "Branch_EIRP_dBm": mapl["Branch_EIRP_dBm"],
        "Radio_Data_Source": mapl["Radio_Data_Source"],
        "Frequency_MHz": frequency["frequency_mhz"],
        "Frequency_Source": frequency["source"],
        "Bandwidth_MHz": mapl["Bandwidth_MHz"],
        "SCS_kHz": mapl["SCS_kHz"],
        "RB_Count": mapl["RB_Count"],
        "MAPL_Before_Margin_dB": mapl["MAPL_Before_Margin_dB"],
        "Margin_dB": float(margin_db),
        "Additional_Loss_dB": loss["additional_loss_db"],
        "ITU_Environment": environment,
        "ITU_Condition": condition,
        "Environment_Mapping_Reason": environment_reason,
        "Condition_Reason": condition_reason,
        "Area_Efficiency": efficiency["area_efficiency"],
        "Environment_Mapping_Confidence": environment_confidence,
        "Condition_Confidence": condition_confidence,
        "Loss_Calculation_Source": loss["source"],
        "Number_of_required_DOTs_Radios": required_radios,
        "Is_Limiting_Band": False,
        "Override_Fields": ", ".join(override_fields),
        "Warnings": "; ".join(warnings),
    }
    result.update(coverage)
    result["Calculation_Status"] = "warning" if warnings and coverage["Calculation_Status"] == "ok" else coverage["Calculation_Status"]
    result["Result_Valid_For_Planning"] = bool(
        coverage["Frequency_Range_Valid"]
        and (
            coverage["Distance_Range_Valid"]
            or coverage["Coverage_Capped_To_Model_Range"]
        )
    )
    return result


def _error_result(record, mapl_result, message):
    normalized = normalize_building_record(record)
    try:
        mapl = normalize_mapl_result(mapl_result)
    except Exception:
        mapl = {}
    result = {column: None for column in RESULT_COLUMNS}
    result.update({
        "Area_ID": str(normalized.get("Area_ID", "")).strip(),
        "Building_Name": str(normalized.get("Building_Name", "")).strip(),
        "Building_Type": str(normalized.get("Building_Type", "")).strip(),
        "Category": str(normalized.get("Category", "")).strip(),
        "Sub_Type": str(normalized.get("Sub_Type_A", "")).strip(),
        "Area_Coverage_sqft": normalized.get("Coverage Area"),
        "Technology": mapl.get("Technology"),
        "Band": mapl.get("Band"),
        "Dot_Model": mapl.get("Dot_Model"),
        "Dot_Variant_KRY": mapl.get("Dot_Variant_KRY"),
        "Duplex_Mode": mapl.get("Duplex_Mode"),
        "Tx_Branch_Count": mapl.get("Tx_Branch_Count"),
        "Effective_Tx_Power_dBm_per_Branch": mapl.get("Effective_Tx_Power_dBm_per_Branch"),
        "Antenna_Gain_dBi": mapl.get("Antenna_Gain_dBi"),
        "Branch_EIRP_dBm": mapl.get("Branch_EIRP_dBm"),
        "Radio_Data_Source": mapl.get("Radio_Data_Source"),
        "Coverage_Type": "lte_coverage" if mapl.get("Technology") == "LTE" else "nr_coverage" if mapl.get("Technology") == "NR" else None,
        "MAPL_Before_Margin_dB": mapl.get("MAPL_Before_Margin_dB"),
        "Is_Limiting_Band": False,
        "Calculation_Status": "error",
        "Result_Valid_For_Planning": False,
        "Warnings": str(message),
    })
    return result


def _normalize_mapl_collection(mapl_results):
    if isinstance(mapl_results, pd.DataFrame):
        if {"Parameter", "Value"}.issubset(mapl_results.columns):
            return [mapl_results]
        return [row for _, row in mapl_results.iterrows()]
    if isinstance(mapl_results, Mapping):
        return [mapl_results]
    if isinstance(mapl_results, (list, tuple)):
        return list(mapl_results)
    raise TypeError("mapl_results must be a mapping, list, tuple, or pandas.DataFrame.")


def calculate_coverage_for_all_buildings(building_df, mapl_results, margin_db=6.0, overrides=None):
    if isinstance(building_df, pd.Series):
        buildings = pd.DataFrame([building_df.to_dict()])
    elif isinstance(building_df, Mapping):
        buildings = pd.DataFrame([dict(building_df)])
    elif isinstance(building_df, pd.DataFrame):
        buildings = building_df.copy()
    else:
        raise TypeError("building_df must be a mapping, pandas.Series, or pandas.DataFrame.")

    mapl_collection = _normalize_mapl_collection(mapl_results)
    overrides = overrides or {}
    results = []
    for row_number, (_, building_row) in enumerate(buildings.iterrows(), start=1):
        building = normalize_building_record(building_row)
        if not str(building.get("Area_ID", "")).strip():
            building["Area_ID"] = f"area-{row_number}"
        building_override = overrides.get(building["Area_ID"], overrides.get(str(building.get("Sub_Type_A", "")).strip(), {}))
        for mapl_result in mapl_collection:
            try:
                results.append(calculate_building_coverage(building, mapl_result, margin_db=margin_db, overrides=building_override))
            except Exception as error:
                results.append(_error_result(building, mapl_result, error))

    result_df = pd.DataFrame(results).reindex(columns=RESULT_COLUMNS)
    if result_df.empty:
        return result_df
    valid_rows = result_df[
        result_df["Planning_Area_sqft"].notna()
        & result_df["Area_ID"].notna()
        & result_df["Technology"].notna()
    ]
    for _, group in valid_rows.groupby(["Area_ID", "Technology"], dropna=False):
        limiting_index = group["Planning_Area_sqft"].astype(float).idxmin()
        result_df.loc[limiting_index, "Is_Limiting_Band"] = True
    result_df["Is_Limiting_Band"] = result_df["Is_Limiting_Band"].fillna(False).astype(bool)
    return result_df

def summarize_building_equipment(coverage_result_df, dots_per_iru=7, irus_per_bbu=12):
    """Summarize valid limiting coverage rows into whole-unit equipment counts."""
    if not isinstance(coverage_result_df, pd.DataFrame):
        raise TypeError("coverage_result_df must be a pandas.DataFrame.")
    if dots_per_iru <= 0 or irus_per_bbu <= 0:
        raise ValueError("Equipment conversion ratios must be positive.")

    required_columns = {
        "Area_Coverage_sqft",
        "Planning_Area_sqft",
        "Number_of_required_DOTs_Radios",
    }
    missing_columns = sorted(required_columns.difference(coverage_result_df.columns))
    if missing_columns:
        raise ValueError(
            "Coverage results are missing required columns: " + ", ".join(missing_columns)
        )

    planning_rows = coverage_result_df.copy()
    if "Result_Valid_For_Planning" in planning_rows.columns:
        planning_rows = planning_rows[
            planning_rows["Result_Valid_For_Planning"].fillna(False).astype(bool)
        ]
    planning_rows = planning_rows[
        pd.to_numeric(planning_rows["Area_Coverage_sqft"], errors="coerce").notna()
        & pd.to_numeric(planning_rows["Planning_Area_sqft"], errors="coerce").gt(0)
    ]

    if "Is_Limiting_Band" in planning_rows.columns:
        limiting_rows = planning_rows[
            planning_rows["Is_Limiting_Band"].fillna(False).astype(bool)
        ]
        if not limiting_rows.empty:
            planning_rows = limiting_rows

    total_area_sqft = float(
        pd.to_numeric(planning_rows["Area_Coverage_sqft"], errors="coerce").fillna(0).sum()
    )
    total_required_radios = int(
        pd.to_numeric(
            planning_rows["Number_of_required_DOTs_Radios"],
            errors="coerce",
        ).fillna(0).clip(lower=0).sum()
    )
    average_sqft_per_dot = (
        total_area_sqft / total_required_radios if total_required_radios else 0.0
    )
    total_irus = math.ceil(total_required_radios / dots_per_iru) if total_required_radios else 0
    total_bbus = math.ceil(total_irus / irus_per_bbu) if total_irus else 0

    return {
        "Total_Coverage_Area_sqft": total_area_sqft,
        "Average_sqft_per_DOT_Radio": average_sqft_per_dot,
        "Total_Required_DOTs_Radios": total_required_radios,
        "Total_IRUs": total_irus,
        "Total_BBUs": total_bbus,
        "DOTs_per_IRU": float(dots_per_iru),
        "IRUs_per_BBU": int(irus_per_bbu),
    }
