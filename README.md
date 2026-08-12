# Ericsson RF ROM Tool

Streamlit intake, MAPL, and indoor LTE/NR coverage estimation for Neutral Host and Enterprise Private 5G planning.

## Engineering Documentation

See [docs/RF_ROM_TOOL_ENGINEERING_GUIDE.md](docs/RF_ROM_TOOL_ENGINEERING_GUIDE.md) for the complete RF-engineering guide. It explains the intake state machine, Excel and CSV dependencies, variable mappings, indoor radio lookup, LTE/NR MAPL formulas, ITU indoor coverage model, area allocation, required-radio calculation, validation rules, worked examples, and current engineering limitations.

## Run

Full engineering UI:

```powershell
streamlit run main.py --server.port 8507
```

Simplified user UI:

```powershell
streamlit run simplified_ui.py --server.port 8508
```

Both entry points use the same `radio_reference.py`, `coverage_engine.py`, RF reference CSV, and building-assumption workbook.

## Indoor Radio RF Reference

The reusable Ericsson indoor radio source is [`data/ericsson_radio_dot_rf.csv`](data/ericsson_radio_dot_rf.csv). Each row represents one unique model, KRY/KRC variant, band, supported-technology set, and duplex-mode combination.

Fields:

| Field | Meaning |
| --- | --- |
| `dot_model` | Normalized radio model, such as `DOT 4455` or `Micro Radio 4402`. |
| `dot_variant_kry` | Exact KRY or KRC hardware variant. |
| `band` | Normalized RF band. |
| `frequency_type` | Human-readable spectrum family. |
| `frequency_min_mhz`, `frequency_max_mhz` | Supported operating-frequency range. |
| `technology` | Informational slash-delimited support list; MAPL uses LTE or NR only. |
| `duplex_mode` | FDD or TDD. |
| `tx_branch_count` | Radio transmit branches; retained for MIMO/capacity reporting. |
| `default_tx_power_dbm_per_branch` | Default single-carrier transmit power for one RF branch. |
| `antenna_gain_dbi` | Reference antenna gain used for the selected Dot or Micro Radio configuration. |
| `power_note` | Configuration or regulatory note. |

`radio_reference.py` loads and validates the table, normalizes legacy names, resolves unique variants, builds a typed `RadioMaplConfig`, and calculates MAPL.

## Lookup Hierarchy

1. Normalize Dot aliases such as `4455`, `RD4455`, and `Radio Dot 4455` to `DOT 4455`; normalize Micro aliases such as `Micro_4408` and `Micro4408` to `Micro Radio 4408`.
2. Normalize unambiguous band aliases such as `B2/B25` to `B25`, `B4/B66` to `B66`, `B48-CBRS` to `B48`, and `N77/C-Band` to `B77D`.
3. Match model, optional KRY/KRC variant, band, and LTE/NR technology.
4. Infer a hardware variant only when model and band identify one row. `DOT 4455 B77D` requires an explicit KRY because two antenna gains exist; Micro Radio KRC variants are inferred when model and band are unique.
5. Use an exact configured carrier frequency when present; otherwise use the reference-range midpoint and return a warning.

Unsupported model/band/technology combinations, out-of-range frequencies, invalid bandwidth/SCS pairs, conflicting table rows, and missing ambiguous variants return clear validation errors.

## Existing Input Mapping

| Existing application value | Radio schema field |
| --- | --- |
| `dot_type` | `dot_model` |
| `dot_variant_kry` | `dot_variant_kry` |
| `Limit_freq_type` | `band` |
| `Operator_type` plus `Coverage_type` | `technology` |
| RF reference row | `duplex_mode`, `tx_branch_count`, default power, antenna gain, frequency range |
| Advanced frequency override or range midpoint | `carrier_frequency_mhz` |
| Current LTE/NR defaults | `bandwidth_mhz`, `scs_khz` |
| `Max_lim_channel_count` | `carrier_count` |
| `target_rsrp` | `target_rsrp_dbm` |
| Hidden Streamlit design policy | `margin_db` |

LTE currently defaults to 20 MHz. NR currently defaults to 40 MHz at 30 kHz SCS. The live Streamlit workflow currently passes a hidden fixed 18 dB design margin. These values are centralized in the MAPL configuration mapping so later intake fields can replace them without changing the RF formula.

## Power and MAPL Rules

Transmit power is per RF branch. Branch EIRP is:

```python
branch_eirp_dbm = effective_tx_power_dbm_per_branch + antenna_gain_dbi
```

MIMO branch powers are not combined for LTE RSRP or NR SS-RSRP MAPL, so the calculation does not add `10 * log10(tx_branch_count)`. The branch count is preserved for later capacity, aggregate-power, and implementation-gain work.

The current ROM fixes highest-band channel count to one. When more than one operator uses the highest band, the UI automatically treats the selected table or overridden branch power as shared equally across those operators:

```python
per_operator_tx_power_dbm = total_tx_power_dbm_per_branch - 10 * log10(operator_count)
```

No sharing loss is applied when operator count is one. A validated user transmit-power override takes precedence over the table default and is identified in output. Numeric transmit-power values come directly from the CSV. The current Micro Radio rows use 37 dBm (5 W) per branch. B48 selections return a warning because SAS-authorized EIRP or PSD constraints may reduce actual CBRS power; no unverified reduction is invented. Antenna assumptions in `power_note` remain visible engineering context.

MAPL uses the existing LTE and NR resource-block tables. Antenna gain is included in branch EIRP exactly once. `MAPL_Before_Margin_dB` is passed to the coverage engine, where the selected design margin is applied exactly once; transmit power and antenna gain are not added again in coverage.

## Examples

LTE lookup:

```python
from radio_reference import get_radio_dot_characteristics

characteristics = get_radio_dot_characteristics(
    dot_model="DOT 4455",
    dot_variant_kry="KRY 901 523/1",
    band="B66",
    technology="LTE",
)
```

NR MAPL:

```python
from radio_reference import build_radio_mapl_config, calculate_mapl

characteristics = get_radio_dot_characteristics(
    dot_model="DOT 4459",
    dot_variant_kry=None,
    band="B48",
    technology="NR",
)
config = build_radio_mapl_config(
    user_inputs={
        "dot_model": "DOT 4459",
        "band": "B48",
        "technology": "NR",
        "target_rsrp_dbm": -95,
        "margin_db": 18,
        "carrier_count": 1,
    },
    radio_reference=characteristics,
)
mapl_result = calculate_mapl(config)
```

Micro Radio lookup:

```python
characteristics = get_radio_dot_characteristics(
    dot_model="Micro Radio 4408",
    dot_variant_kry=None,
    band="B48",
    technology="NR",
)
```

The Streamlit model, variant, band, power, branch count, antenna gain, duplex mode, and operating range now come from the CSV for both Radio Dot and Micro Radio selections. Micro Radio coverage counts are calculated, but IRU/BBU conversion is intentionally not displayed because the RF table does not define a Micro Radio-to-baseband equipment ratio.

For DOT-IRU-BBU selections, Enterprise Private 5G exposes DOT 4459 only; Enterprise 5G Coverage exposes DOT 2274 and DOT 4455 only. Coverage Focused equipment summaries use 7 DOTs per IRU, while Capacity Focused summaries use 5.5 DOTs per IRU. The guided intake supports targeted field edits after completion and recalculates dependent selections when an upstream answer changes.

## Extending the Table

Add one CSV row for each unique model, KRY/KRC variant, band, technology-support set, and duplex combination. Use numeric MHz minimum/maximum fields, per-branch dBm, and dBi. Do not add model-specific RF constants to Streamlit code. Run the test suite after every reference update:

```powershell
python -m unittest discover -s tests -v
```

Duplicate or conflicting lookup rows are rejected when the table loads.
