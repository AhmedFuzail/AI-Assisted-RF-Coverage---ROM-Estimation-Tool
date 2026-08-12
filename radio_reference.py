"""Ericsson indoor radio RF lookup, validation, and MAPL configuration."""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


DATA_SOURCE = "Ericsson indoor radio RF reference table"
RADIO_REFERENCE_PATH = Path(__file__).resolve().parent / "data" / "ericsson_radio_dot_rf.csv"

LTE_RB_TABLE = {
    1.4: 6,
    3.0: 15,
    5.0: 25,
    10.0: 50,
    15.0: 75,
    20.0: 100,
}

NR_FR1_RB_TABLE = {
    15: {5.0: 25, 10.0: 52, 15.0: 79, 20.0: 106, 25.0: 133, 30.0: 160, 40.0: 216, 50.0: 270},
    30: {5.0: 11, 10.0: 24, 15.0: 38, 20.0: 51, 25.0: 65, 30.0: 78, 40.0: 106, 50.0: 133, 60.0: 162, 70.0: 189, 80.0: 217, 90.0: 245, 100.0: 273},
    60: {10.0: 11, 15.0: 18, 20.0: 24, 25.0: 31, 30.0: 38, 40.0: 51, 50.0: 65, 60.0: 79, 70.0: 93, 80.0: 107, 90.0: 121, 100.0: 135},
}

_REQUIRED_COLUMNS = {
    "dot_model",
    "dot_variant_kry",
    "band",
    "frequency_type",
    "frequency_min_mhz",
    "frequency_max_mhz",
    "technology",
    "duplex_mode",
    "tx_branch_count",
    "default_tx_power_dbm_per_branch",
    "antenna_gain_dbi",
    "power_note",
}


@dataclass(frozen=True)
class RadioDotCharacteristics:
    dot_model: str
    dot_variant_kry: str
    band: str
    frequency_type: str
    frequency_min_mhz: float
    frequency_max_mhz: float
    supported_technologies: tuple[str, ...]
    duplex_mode: str
    tx_branch_count: int
    default_tx_power_dbm_per_branch: float
    antenna_gain_dbi: float
    power_note: str
    warnings: tuple[str, ...] = ()
    data_source: str = DATA_SOURCE

    @property
    def carrier_frequency_mhz(self) -> float:
        return (self.frequency_min_mhz + self.frequency_max_mhz) / 2.0


@dataclass(frozen=True)
class RadioMaplConfig:
    dot_model: str
    dot_variant_kry: str
    band: str
    technology: str
    duplex_mode: str
    carrier_frequency_mhz: float
    bandwidth_mhz: float
    scs_khz: float | None
    tx_branch_count: int
    configured_tx_power_dbm_per_branch: float
    antenna_gain_dbi: float
    carrier_count: int
    target_rsrp_dbm: float
    margin_db: float = 6.0
    default_tx_power_dbm_per_branch: float = 0.0
    power_is_total_across_carriers: bool = False
    power_share_count: int = 1
    power_note: str = ""
    warnings: tuple[str, ...] = ()
    override_fields: tuple[str, ...] = ()
    value_sources: Mapping[str, str] = field(default_factory=dict)
    data_source: str = DATA_SOURCE


def normalize_radio_model(value: Any) -> str:
    text = str(value or "").strip().upper()
    match = re.search(r"(\d{4})", text)
    if not match:
        raise ValueError(f"Unsupported radio model: {value or 'blank'}.")
    if "MICRO" in text:
        return f"Micro Radio {match.group(1)}"
    return f"DOT {match.group(1)}"


def normalize_dot_model(value: Any) -> str:
    """Backward-compatible alias for radio model normalization."""
    return normalize_radio_model(value)


def normalize_variant_kry(value: Any) -> str:
    text = " ".join(str(value or "").strip().upper().split())
    if not text:
        return ""
    prefixed = re.match(r"^(KRY|KRC)\s*(.*)$", text)
    if prefixed:
        return f"{prefixed.group(1)} {prefixed.group(2).strip()}"
    return f"KRY {text}"


def normalize_technology(value: Any) -> str:
    technology = str(value or "").strip().upper()
    if technology in {"4G", "LTE"}:
        return "LTE"
    if technology in {"5G", "NR", "5G NR"}:
        return "NR"
    raise ValueError(f"Unsupported technology: {value or 'blank'}. Use LTE or NR.")


def normalize_band(value: Any) -> str:
    text = str(value or "").strip().upper()
    compact = re.sub(r"[^A-Z0-9/]", "", text)
    aliases = {
        "25": "B25",
        "B25": "B25",
        "BAND25": "B25",
        "PCS": "B25",
        "B2/B25": "B25",
        "B2B25": "B25",
        "66": "B66",
        "B66": "B66",
        "BAND66": "B66",
        "AWS": "B66",
        "B4/B66": "B66",
        "B4B66": "B66",
        "41": "B41",
        "B41": "B41",
        "BAND41": "B41",
        "B41K": "B41K",
        "48": "B48",
        "B48": "B48",
        "BAND48": "B48",
        "CBRS": "B48",
        "B48CBRS": "B48",
        "B77D": "B77D",
        "B77G": "B77G",
        "N77": "B77D",
        "N77/CBAND": "B77D",
        "N77CBAND": "B77D",
        "CBAND": "B77D",
    }
    normalized = aliases.get(compact)
    if not normalized:
        raise ValueError(f"Unsupported or ambiguous band: {value or 'blank'}.")
    return normalized


def _to_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be numeric.") from error
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _to_positive_int(value: Any, field_name: str) -> int:
    number = _to_float(value, field_name)
    if number < 1 or not number.is_integer():
        raise ValueError(f"{field_name} must be a positive whole number.")
    return int(number)


@lru_cache(maxsize=8)
def _load_reference(reference_path: str, modified_ns: int) -> tuple[RadioDotCharacteristics, ...]:
    path = Path(reference_path)
    if not path.exists():
        raise FileNotFoundError(f"Radio RF reference table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = _REQUIRED_COLUMNS.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Radio Dot RF table is missing columns: {', '.join(sorted(missing))}.")
        rows = list(reader)

    results = []
    lookup_keys = set()
    for row_number, row in enumerate(rows, start=2):
        dot_model = normalize_radio_model(row["dot_model"])
        variant = normalize_variant_kry(row["dot_variant_kry"])
        band = normalize_band(row["band"])
        technologies = tuple(dict.fromkeys(
            normalize_technology(item)
            for item in row["technology"].split("/")
            if item.strip().upper() != "WCDMA"
        ))
        if not technologies:
            raise ValueError(f"Row {row_number} has no LTE or NR technology.")
        duplex_key = row["duplex_mode"].strip().upper()
        row_keys = [(dot_model, variant, band, technology, duplex_key) for technology in technologies]
        conflicting_keys = [key for key in row_keys if key in lookup_keys]
        if conflicting_keys:
            raise ValueError(
                f"Duplicate or conflicting radio RF reference row at CSV row {row_number}: "
                f"{conflicting_keys[0]}."
            )
        lookup_keys.update(row_keys)

        frequency_min = _to_float(row["frequency_min_mhz"], "frequency_min_mhz")
        frequency_max = _to_float(row["frequency_max_mhz"], "frequency_max_mhz")
        if frequency_min <= 0 or frequency_max <= frequency_min:
            raise ValueError(f"Invalid frequency range at CSV row {row_number}.")
        duplex_mode = row["duplex_mode"].strip().upper()
        if duplex_mode not in {"FDD", "TDD"}:
            raise ValueError(f"Invalid duplex_mode at CSV row {row_number}: {duplex_mode}.")

        warnings = []
        power_note = row["power_note"].strip()
        if power_note and power_note.lower() != "standard default":
            warnings.append(power_note)
        documented_power = re.search(r"use\s+(-?\d+(?:\.\d+)?)\s*dBm", power_note, re.IGNORECASE)
        numeric_power = _to_float(row["default_tx_power_dbm_per_branch"], "default_tx_power_dbm_per_branch")
        if documented_power and not math.isclose(float(documented_power.group(1)), numeric_power, abs_tol=0.05):
            warnings.append(
                f"RF reference power mismatch: numeric default is {numeric_power:g} dBm per branch, "
                f"while power_note states {documented_power.group(1)} dBm. The numeric field was used."
            )
        if band == "B48":
            warnings.append("Actual CBRS power may be lower because of SAS-authorized EIRP or PSD limits.")
        results.append(RadioDotCharacteristics(
            dot_model=dot_model,
            dot_variant_kry=variant,
            band=band,
            frequency_type=row["frequency_type"].strip(),
            frequency_min_mhz=frequency_min,
            frequency_max_mhz=frequency_max,
            supported_technologies=technologies,
            duplex_mode=duplex_mode,
            tx_branch_count=_to_positive_int(row["tx_branch_count"], "tx_branch_count"),
            default_tx_power_dbm_per_branch=numeric_power,
            antenna_gain_dbi=_to_float(row["antenna_gain_dbi"], "antenna_gain_dbi"),
            power_note=power_note,
            warnings=tuple(warnings),
        ))
    return tuple(results)


def load_radio_dot_reference(reference_path: str | Path = RADIO_REFERENCE_PATH) -> tuple[RadioDotCharacteristics, ...]:
    path = Path(reference_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Radio RF reference table not found: {path}")
    return _load_reference(str(path), path.stat().st_mtime_ns)


def get_radio_dot_characteristics(
    dot_model: str,
    dot_variant_kry: str | None,
    band: str,
    technology: str,
    reference_path: str | Path = RADIO_REFERENCE_PATH,
) -> RadioDotCharacteristics:
    model = normalize_radio_model(dot_model)
    variant = normalize_variant_kry(dot_variant_kry)
    normalized_band = normalize_band(band)
    normalized_technology = normalize_technology(technology)
    reference = load_radio_dot_reference(reference_path)

    model_rows = [row for row in reference if row.dot_model == model]
    if not model_rows:
        raise ValueError(f"Unsupported radio model: {model}.")
    band_rows = [row for row in model_rows if row.band == normalized_band]
    if not band_rows:
        supported = ", ".join(sorted({row.band for row in model_rows}))
        raise ValueError(f"{model} does not support {normalized_band}. Supported bands: {supported}.")
    if variant:
        variant_rows = [row for row in band_rows if row.dot_variant_kry == variant]
        if not variant_rows:
            supported = ", ".join(sorted({row.dot_variant_kry for row in band_rows}))
            raise ValueError(f"{model} {normalized_band} does not support {variant}. Available variants: {supported}.")
        band_rows = variant_rows

    technology_rows = [row for row in band_rows if normalized_technology in row.supported_technologies]
    if not technology_rows:
        supported = ", ".join(sorted({tech for row in band_rows for tech in row.supported_technologies}))
        raise ValueError(
            f"{normalized_technology} is not supported for {model} {normalized_band}"
            f"{f' {variant}' if variant else ''}. Supported technologies: {supported}."
        )
    variants = sorted({row.dot_variant_kry for row in technology_rows})
    if not variant and len(variants) > 1:
        raise ValueError(
            f"{model} {normalized_band} has more than one hardware variant. Select either "
            f"{' or '.join(variants)} because the antenna gains differ."
        )
    if len(technology_rows) != 1:
        raise ValueError(f"Conflicting radio RF reference rows found for {model}, {normalized_band}, and {normalized_technology}.")
    return technology_rows[0]


def get_radio_dot_models(reference_path: str | Path = RADIO_REFERENCE_PATH) -> list[str]:
    return sorted({row.dot_model for row in load_radio_dot_reference(reference_path)})


def get_radio_dot_variants(
    dot_model: str,
    technology: str | None = None,
    reference_path: str | Path = RADIO_REFERENCE_PATH,
) -> list[str]:
    model = normalize_radio_model(dot_model)
    rows = [row for row in load_radio_dot_reference(reference_path) if row.dot_model == model]
    if technology:
        normalized_technology = normalize_technology(technology)
        rows = [row for row in rows if normalized_technology in row.supported_technologies]
    return sorted({row.dot_variant_kry for row in rows})


def get_supported_bands(
    dot_model: str,
    dot_variant_kry: str | None = None,
    technology: str | None = None,
    reference_path: str | Path = RADIO_REFERENCE_PATH,
) -> list[str]:
    model = normalize_radio_model(dot_model)
    variant = normalize_variant_kry(dot_variant_kry)
    rows = [row for row in load_radio_dot_reference(reference_path) if row.dot_model == model]
    if variant:
        rows = [row for row in rows if row.dot_variant_kry == variant]
    if technology:
        normalized_technology = normalize_technology(technology)
        rows = [row for row in rows if normalized_technology in row.supported_technologies]
    return sorted({row.band for row in rows})


def _mapping_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def build_radio_mapl_config(
    user_inputs: Mapping[str, Any],
    calculated_data: Mapping[str, Any] | None = None,
    radio_reference: RadioDotCharacteristics | None = None,
) -> RadioMaplConfig:
    calculated_data = calculated_data or {}
    model = _mapping_value(user_inputs, "dot_model", "dot_type") or _mapping_value(calculated_data, "dot_model", "dot_type")
    variant = _mapping_value(user_inputs, "dot_variant_kry") or _mapping_value(calculated_data, "dot_variant_kry")
    band = _mapping_value(user_inputs, "band", "limiting_band", "Limit_freq_type") or _mapping_value(calculated_data, "band", "limiting_band")
    technology = _mapping_value(user_inputs, "technology") or _mapping_value(calculated_data, "technology", "Technology")
    if radio_reference is None:
        radio_reference = get_radio_dot_characteristics(model, variant, band, technology)

    override_fields = []
    value_sources = {
        "duplex_mode": DATA_SOURCE,
        "tx_branch_count": DATA_SOURCE,
        "antenna_gain_dbi": DATA_SOURCE,
    }
    warnings = list(radio_reference.warnings)

    user_frequency = _mapping_value(user_inputs, "carrier_frequency_mhz", "frequency_mhz")
    project_frequency = _mapping_value(calculated_data, "carrier_frequency_mhz", "frequency_mhz", "Frequency_MHz")
    if user_frequency is not None:
        carrier_frequency = _to_float(user_frequency, "carrier_frequency_mhz")
        value_sources["carrier_frequency_mhz"] = "user override"
        override_fields.append("carrier_frequency_mhz")
    elif project_frequency is not None:
        carrier_frequency = _to_float(project_frequency, "carrier_frequency_mhz")
        value_sources["carrier_frequency_mhz"] = "existing project value"
    else:
        carrier_frequency = radio_reference.carrier_frequency_mhz
        value_sources["carrier_frequency_mhz"] = "reference-range midpoint"
        warnings.append(
            f"Carrier frequency defaulted to the {radio_reference.band} reference-range midpoint "
            f"({carrier_frequency:g} MHz)."
        )
    if not radio_reference.frequency_min_mhz <= carrier_frequency <= radio_reference.frequency_max_mhz:
        raise ValueError(
            f"Carrier frequency {carrier_frequency:g} MHz is outside the supported {radio_reference.band} range "
            f"of {radio_reference.frequency_min_mhz:g}-{radio_reference.frequency_max_mhz:g} MHz."
        )

    normalized_technology = normalize_technology(technology)
    bandwidth_value = _mapping_value(user_inputs, "bandwidth_mhz")
    bandwidth_source = "user override"
    if bandwidth_value is None:
        bandwidth_value = _mapping_value(calculated_data, "bandwidth_mhz", "Bandwidth_MHz")
        bandwidth_source = "existing project value"
    if bandwidth_value is None:
        bandwidth_value = 20.0 if normalized_technology == "LTE" else 40.0
        bandwidth_source = "application default"
    bandwidth = _to_float(bandwidth_value, "bandwidth_mhz")
    value_sources["bandwidth_mhz"] = bandwidth_source
    if bandwidth_source == "user override":
        override_fields.append("bandwidth_mhz")

    scs_value = _mapping_value(user_inputs, "scs_khz")
    scs_source = "user override"
    if scs_value is None:
        scs_value = _mapping_value(calculated_data, "scs_khz", "SCS_kHz")
        scs_source = "existing project value"
    if normalized_technology == "NR" and scs_value is None:
        scs_value = 30.0
        scs_source = "application default"
    scs = _to_float(scs_value, "scs_khz") if scs_value is not None else None
    value_sources["scs_khz"] = scs_source if scs is not None else "LTE fixed 15 kHz"
    if scs_source == "user override" and scs is not None:
        override_fields.append("scs_khz")

    user_power = _mapping_value(user_inputs, "configured_tx_power_dbm_per_branch", "tx_power_dbm_per_branch")
    project_power = _mapping_value(calculated_data, "configured_tx_power_dbm_per_branch", "tx_power_dbm_per_branch")
    if user_power is not None:
        configured_power = _to_float(user_power, "configured_tx_power_dbm_per_branch")
        value_sources["configured_tx_power_dbm_per_branch"] = "user override"
        override_fields.append("configured_tx_power_dbm_per_branch")
        warnings.append("Using user-configured Tx power instead of the Radio Dot default.")
    elif project_power is not None:
        configured_power = _to_float(project_power, "configured_tx_power_dbm_per_branch")
        value_sources["configured_tx_power_dbm_per_branch"] = "existing project value"
    else:
        configured_power = radio_reference.default_tx_power_dbm_per_branch
        value_sources["configured_tx_power_dbm_per_branch"] = DATA_SOURCE
    if configured_power < -10 or configured_power > 40:
        raise ValueError("configured_tx_power_dbm_per_branch must be between -10 and 40 dBm.")

    carrier_count_value = _mapping_value(user_inputs, "carrier_count", "Max_lim_channel_count")
    if carrier_count_value is None:
        carrier_count_value = _mapping_value(calculated_data, "carrier_count") or 1
    carrier_count = _to_positive_int(carrier_count_value, "carrier_count")
    power_share_count_value = _mapping_value(user_inputs, "power_share_count", "Operator_count")
    operator_share_was_provided = power_share_count_value is not None
    if power_share_count_value is None:
        power_share_count_value = _mapping_value(calculated_data, "power_share_count") or carrier_count
    power_share_count = _to_positive_int(power_share_count_value, "power_share_count")
    power_sharing_value = _mapping_value(
        user_inputs,
        "power_is_total_across_carriers",
        "power_sharing",
    )
    power_is_total = (
        power_share_count > 1
        if power_sharing_value is None and operator_share_was_provided
        else bool(power_sharing_value or False)
    )

    target_value = _mapping_value(user_inputs, "target_rsrp_dbm", "target_rsrp")
    if target_value is None:
        target_value = _mapping_value(calculated_data, "target_rsrp_dbm", "Target_RSRP_dBm")
    if target_value is None:
        raise ValueError("target_rsrp_dbm is required.")
    target_rsrp = _to_float(target_value, "target_rsrp_dbm")
    if not -140 <= target_rsrp <= -40:
        raise ValueError("target_rsrp_dbm must be between -140 and -40 dBm.")

    margin_value = _mapping_value(user_inputs, "margin_db")
    if margin_value is None:
        margin_value = _mapping_value(calculated_data, "margin_db", "Margin_dB")
    margin = _to_float(6.0 if margin_value is None else margin_value, "margin_db")
    if margin < 0 or margin > 30:
        raise ValueError("margin_db must be between 0 and 30 dB.")

    if normalized_technology == "LTE":
        if bandwidth not in LTE_RB_TABLE:
            raise ValueError(f"Unsupported LTE bandwidth: {bandwidth:g} MHz. Supported: {list(LTE_RB_TABLE)}.")
    else:
        if scs is None:
            raise ValueError("scs_khz is required for NR.")
        scs_int = int(scs)
        if scs != scs_int or scs_int not in NR_FR1_RB_TABLE:
            raise ValueError(f"Unsupported NR SCS: {scs:g} kHz. Supported: {list(NR_FR1_RB_TABLE)}.")
        if bandwidth not in NR_FR1_RB_TABLE[scs_int]:
            raise ValueError(
                f"Unsupported NR bandwidth/SCS combination: {bandwidth:g} MHz @ {scs:g} kHz. "
                f"Supported bandwidths: {list(NR_FR1_RB_TABLE[scs_int])}."
            )

    return RadioMaplConfig(
        dot_model=radio_reference.dot_model,
        dot_variant_kry=radio_reference.dot_variant_kry,
        band=radio_reference.band,
        technology=normalized_technology,
        duplex_mode=radio_reference.duplex_mode,
        carrier_frequency_mhz=carrier_frequency,
        bandwidth_mhz=bandwidth,
        scs_khz=scs,
        tx_branch_count=radio_reference.tx_branch_count,
        configured_tx_power_dbm_per_branch=configured_power,
        antenna_gain_dbi=radio_reference.antenna_gain_dbi,
        carrier_count=carrier_count,
        target_rsrp_dbm=target_rsrp,
        margin_db=margin,
        default_tx_power_dbm_per_branch=radio_reference.default_tx_power_dbm_per_branch,
        power_is_total_across_carriers=power_is_total,
        power_share_count=power_share_count,
        power_note=radio_reference.power_note,
        warnings=tuple(dict.fromkeys(warnings)),
        override_fields=tuple(dict.fromkeys(override_fields)),
        value_sources=value_sources,
    )


def calculate_mapl(config: RadioMaplConfig) -> dict[str, Any]:
    technology = normalize_technology(config.technology)
    if technology == "LTE":
        rb_count = LTE_RB_TABLE[float(config.bandwidth_mhz)]
        scs_used = 15.0
    else:
        scs_used = float(config.scs_khz)
        rb_count = NR_FR1_RB_TABLE[int(scs_used)][float(config.bandwidth_mhz)]

    carrier_sharing_loss_db = 0.0
    if config.power_is_total_across_carriers:
        carrier_sharing_loss_db = 10.0 * math.log10(config.power_share_count)
    effective_tx_power = config.configured_tx_power_dbm_per_branch - carrier_sharing_loss_db
    branch_eirp = effective_tx_power + config.antenna_gain_dbi
    total_subcarriers = 12 * rb_count
    power_per_re = branch_eirp - 10.0 * math.log10(total_subcarriers)
    mapl_before_margin = power_per_re - config.target_rsrp_dbm
    final_mapl = mapl_before_margin - config.margin_db
    warnings = list(config.warnings)
    if config.power_is_total_across_carriers and config.power_share_count > 1:
        warnings.append(
            f"Total per-branch power is shared equally across {config.power_share_count} operators/carriers; "
            f"{carrier_sharing_loss_db:.2f} dB was subtracted."
        )

    return {
        "Dot_Model": config.dot_model,
        "Dot_Variant_KRY": config.dot_variant_kry,
        "Band": config.band,
        "Technology": technology,
        "Duplex_Mode": config.duplex_mode,
        "Frequency_MHz": config.carrier_frequency_mhz,
        "Frequency_Source": config.value_sources.get("carrier_frequency_mhz", ""),
        "Bandwidth_MHz": config.bandwidth_mhz,
        "SCS_kHz": scs_used,
        "Tx_Branch_Count": config.tx_branch_count,
        "Default_Tx_Power_dBm_per_Branch": config.default_tx_power_dbm_per_branch,
        "Configured_Tx_Power_dBm_per_Branch": config.configured_tx_power_dbm_per_branch,
        "Effective_Tx_Power_dBm_per_Branch": effective_tx_power,
        "Antenna_Gain_dBi": config.antenna_gain_dbi,
        "Branch_EIRP_dBm": branch_eirp,
        "Carrier_Count": config.carrier_count,
        "Power_Share_Count": config.power_share_count,
        "Power_Is_Total_Across_Carriers": config.power_is_total_across_carriers,
        "Carrier_Sharing_Loss_dB": carrier_sharing_loss_db,
        "RB_Count": rb_count,
        "Total_Subcarriers": total_subcarriers,
        "Power_Per_RB_or_RE_dBm": power_per_re,
        "Power_Per_RE_dBm": power_per_re,
        "Target_RSRP_dBm": config.target_rsrp_dbm,
        "Margin_dB": config.margin_db,
        "MAPL_Before_Margin_dB": mapl_before_margin,
        "Final_MAPL_dB": final_mapl,
        "Max_Power_mW": 10.0 ** (effective_tx_power / 10.0),
        "Total_Power_dBm": effective_tx_power,
        "Power_Source": config.value_sources.get("configured_tx_power_dbm_per_branch", ""),
        "Warnings": "; ".join(dict.fromkeys(warnings)),
        "Override_Fields": ", ".join(config.override_fields),
        "Data_Source": config.data_source,
    }


def reference_table_display_rows(reference_path: str | Path = RADIO_REFERENCE_PATH) -> list[dict[str, Any]]:
    rows = []
    for item in load_radio_dot_reference(reference_path):
        rows.append({
            "Radio": item.dot_model,
            "Hardware variant": item.dot_variant_kry,
            "Band": item.band,
            "Frequency": f"{item.frequency_min_mhz:g}-{item.frequency_max_mhz:g} MHz",
            "Technology / duplex": f"{'/'.join(item.supported_technologies)} / {item.duplex_mode}",
            "Tx branches": item.tx_branch_count,
            "Tx power per branch": f"{item.default_tx_power_dbm_per_branch:g} dBm",
            "Antenna gain": f"{item.antenna_gain_dbi:g} dBi",
        })
    return rows
