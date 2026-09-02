import streamlit as st
import os
import pandas as pd
import json
from html import escape
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from coverage_engine import (
    calculate_coverage_for_all_buildings,
    resolve_technology,
    resolve_streamlit_design_margin_db,
    summarize_building_equipment,
)
from radio_reference import (
    build_radio_mapl_config,
    calculate_mapl,
    default_bandwidth_mhz,
    get_radio_dot_characteristics,
    get_radio_dot_variants,
    get_radio_dot_models,
    get_supported_bands,
)
from structure_editor_state import (
    apply_area_percentage_edits,
    reconcile_area_percentages,
)
st.set_page_config(
    page_title="Ericsson RF ROM Tool - Simplified",
    page_icon="static/Ericsson_icon.png",
    layout="wide",
)

#st.write("Hello World!")

st.markdown(
    """
    <style>
    [data-testid="stImage"] img {
        border-radius: 0px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

import base64

def load_ttf_font(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

font_regular = load_ttf_font("fonts/EricssonHilda-Regular.ttf")
font_bold = load_ttf_font("fonts/EricssonHilda-Bold.ttf")

st.markdown(f"""
<style>
@font-face {{
    font-family: 'Hilda';
    src: url(data:font/ttf;base64,{font_regular}) format('truetype');
    font-weight: 400;
}}

@font-face {{
    font-family: 'Hilda';
    src: url(data:font/ttf;base64,{font_bold}) format('truetype');
    font-weight: 700;
}}

html, body, [class*="css"] {{
    font-family: 'Hilda', sans-serif;
}}
</style>
""", unsafe_allow_html=True)


ericsson_logo = st.image(os.path.join(os.getcwd(),"static","Ericsson_logo.svg.png"),width=100, )


title_Main = st.title("Ericsson AI-Assisted RF ROM Estimation Tool")


def mapl_result_to_table(result):
    rows = [
        ("Radio Dot", result["Dot_Model"], ""),
        ("Hardware Variant", result["Dot_Variant_KRY"], ""),
        ("Band", result["Band"], ""),
        ("Technology", result["Technology"], ""),
        ("Duplex Mode", result["Duplex_Mode"], ""),
        ("Carrier Frequency", result["Frequency_MHz"], "MHz"),
        ("Bandwidth", result["Bandwidth_MHz"], "MHz"),
        ("SCS", result["SCS_kHz"], "kHz"),
        ("Tx Branches", result["Tx_Branch_Count"], ""),
        ("Default Tx Power Per Branch", result["Default_Tx_Power_dBm_per_Branch"], "dBm"),
        ("Configured Tx Power Per Branch", result["Configured_Tx_Power_dBm_per_Branch"], "dBm"),
        ("Effective Tx Power Per Branch", result["Effective_Tx_Power_dBm_per_Branch"], "dBm"),
        ("Antenna Gain", result["Antenna_Gain_dBi"], "dBi"),
        ("Branch EIRP", result["Branch_EIRP_dBm"], "dBm"),
        ("Carrier Count", result["Carrier_Count"], ""),
        ("Operators Sharing Power", result["Power_Share_Count"], "Operators"),
        ("Operator Power Sharing Loss", result["Carrier_Sharing_Loss_dB"], "dB"),
        ("RB Count", result["RB_Count"], "RB"),
        ("Total Subcarriers", result["Total_Subcarriers"], "Subcarriers"),
        ("Power per RE", result["Power_Per_RE_dBm"], "dBm/RE"),
        ("Target RSRP", result["Target_RSRP_dBm"], "dBm"),
        ("Design Margin", result["Margin_dB"], "dB"),
        ("MAPL Before Margin", result["MAPL_Before_Margin_dB"], "dB"),
        ("Final MAPL", result["Final_MAPL_dB"], "dB"),
        ("Data Source", result["Data_Source"], ""),
        ("Overrides", result["Override_Fields"] or "None", ""),
    ]
    table_df = pd.DataFrame(rows, columns=["Parameter", "Value", "Unit"])
    numeric_mask = table_df["Value"].map(lambda value: isinstance(value, (int, float)))
    table_df.loc[numeric_mask, "Value"] = table_df.loc[numeric_mask, "Value"].map(
        lambda value: f"{value:.2f}".rstrip("0").rstrip(".")
    )
    return table_df

st.divider()

#code_example = """
#def greet(name):
#    print('hello',name)
#"""
#st.code(code_example, language="python")

#button1 = st.button("Press me")
#print(button1)
#reset = st.button("Reset")
#print(reset)
#if reset:
#    (
#    button1==1
#    )
#if button1:
#    (
#    button1==1
#    )

data = {
    "project_id": [101, 102, 103, 104],
    "building_type": ["factory", "warehouse", "office", "hospital"],
    "total_area_sqft": [500000, 300000, 120000, 200000],
    "floors": [1, 1, 3, 5],
    "dense_area_pct": [40, 20, 30, 50],
    "medium_area_pct": [30, 40, 40, 30],
    "open_area_pct": [30, 40, 30, 20],
    "avg_ceiling_height_ft": [35, 30, 12, 10],
    "wall_loss_db": [18, 12, 8, 15],
    "target_rsrp_dbm": [-95, -90, -85, -92],
    "dot_count": [120, 80, 60, 95]   # Target variable
}

df = pd.DataFrame(data)

MAPPING_WORKBOOK_PATH = os.path.join(os.getcwd(), "Sub_Type_RF_Assumptions_Losses.xlsx")


@st.cache_data(show_spinner=False)
def load_building_mapping():
    mapping_df = pd.read_excel(MAPPING_WORKBOOK_PATH, sheet_name="Building_Type")
    mapping_df = mapping_df.dropna(subset=["Building_Type", "Category"])
    mapping_df["Building_Type"] = mapping_df["Building_Type"].astype(str).str.strip()
    mapping_df["Category"] = mapping_df["Category"].astype(str).str.strip()
    mapping_df["Sub_Type_A"] = mapping_df["Sub_Type_A"].astype(str).str.strip()
    return mapping_df


@st.cache_data(show_spinner=False)
def load_unique_assumption_library():
    assumption_df = pd.read_excel(MAPPING_WORKBOOK_PATH, sheet_name="Unique_Assumption_Library")
    assumption_df = assumption_df.dropna(subset=["Sub_Type_A"])
    assumption_df["Sub_Type_A"] = assumption_df["Sub_Type_A"].astype(str).str.strip()
    return assumption_df


building_mapping_df = load_building_mapping()
unique_assumption_df = load_unique_assumption_library()
building_type_options = sorted(building_mapping_df["Building_Type"].dropna().unique().tolist())


def render_structure_note_tooltips(structure_df):
    note_items = []
    for _, row in structure_df.iterrows():
        floorplan_note = escape(str(row.get("RF_Floorplan_Match_Notes", "")))
        sub_type = escape(str(row.get("Sub_Type_A", "")))
        note_items.append(
            f"<span class='subtype-note'>{sub_type} "
            "<span class='info-icon'>i"
            f"<span class='tooltip-text'>{floorplan_note}</span>"
            "</span></span>"
        )

    return f"""
    <style>
    .subtype-note-wrap {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 0.35rem 0 0.85rem 0;
        overflow: visible;
    }}
    .subtype-note {{
        position: relative;
        border: 1px solid #e5e7eb;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        background: #fafafa;
        white-space: nowrap;
        overflow: visible;
    }}
    .info-icon {{
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1rem;
        height: 1rem;
        margin-left: 0.25rem;
        border-radius: 999px;
        border: 1px solid #6b7280;
        color: #374151;
        font-size: 0.72rem;
        font-weight: 700;
        cursor: help;
        line-height: 1;
    }}
    .tooltip-text {{
        visibility: hidden;
        opacity: 0;
        position: absolute;
        z-index: 9999;
        left: 50%;
        bottom: 1.45rem;
        transform: translateX(-50%);
        width: max-content;
        max-width: 28rem;
        white-space: normal;
        text-align: left;
        background: #111827;
        color: #ffffff;
        border-radius: 4px;
        padding: 0.5rem 0.65rem;
        box-shadow: 0 8px 20px rgba(17, 24, 39, 0.18);
        font-size: 0.78rem;
        font-weight: 400;
        line-height: 1.35;
        transition: opacity 0.12s ease-in-out;
    }}
    .info-icon:hover .tooltip-text {{
        visibility: visible;
        opacity: 1;
    }}
    </style>
    <div class='subtype-note-wrap'>{''.join(note_items)}</div>
    """

@st.cache_data(ttl=3600, show_spinner=False)
def search_address_suggestions(query):
    if len(query.strip()) < 3:
        return []

    params = urlencode({
        "q": query.strip(),
        "format": "json",
        "addressdetails": 1,
        "limit": 5,
    })
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": "Ericsson-RF-ROM-UX-Prototype/1.0"},
    )

    try:
        with urlopen(request, timeout=5) as response:
            results = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    return [
        {
            "label": result.get("display_name", "Unknown address"),
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
        }
        for result in results
        if result.get("lat") and result.get("lon")
    ]

if "location_latitude" not in st.session_state:
    st.session_state.location_latitude = 37.493544
if "location_longitude" not in st.session_state:
    st.session_state.location_longitude = -121.945242
if "selected_address" not in st.session_state:
    st.session_state.selected_address = ""
if "show_project_map" not in st.session_state:
    st.session_state.show_project_map = False

st.subheader("Project Location")
address_query = st.text_input(
    "Address (optional)",
    value=st.session_state.selected_address,
    placeholder="Start typing a street address, venue, or city",
)

address_suggestions = search_address_suggestions(address_query)
if address_query.strip() and len(address_query.strip()) < 3:
    st.caption("Type at least 3 characters to search for address suggestions.")
elif address_query.strip() and not address_suggestions:
    st.caption("No address suggestions found yet. You can still enter latitude and longitude manually below.")

if address_suggestions:
    suggestion_labels = [suggestion["label"] for suggestion in address_suggestions]
    selected_address_label = st.selectbox("Suggested addresses", suggestion_labels)
    selected_suggestion = address_suggestions[suggestion_labels.index(selected_address_label)]

    if st.button("Use selected address"):
        st.session_state.selected_address = selected_suggestion["label"]
        st.session_state.location_latitude = selected_suggestion["latitude"]
        st.session_state.location_longitude = selected_suggestion["longitude"]
        st.session_state.show_project_map = True
        st.rerun()

Loc_data = {
    "latitude": [st.session_state.location_latitude],
    "longitude": [st.session_state.location_longitude],
}

df_Loc = pd.DataFrame(Loc_data)
if st.session_state.show_project_map:
    map_loc= st.map(df_Loc, size=75, zoom=14.5, height=225)

st.divider()
markdown_Main = st.header("User Intake")
caption_main = st.caption("Solution and RF details")

intake_steps = [
    {"key": "Customer_name", "label": "Customer Name", "prompt": "Who is the customer?", "description": "Please provide the end customer or enterprise name.", "type": "text", "default": ""},
    {"key": "venue_name", "label": "Venue Name", "prompt": "What is the venue or project name?", "description": "Identify the building, campus, or project this estimate represents.", "type": "text", "default": ""},
    {"key": "total_sqft", "label": "Total Sq.Ft Coverage", "prompt": "How much total indoor coverage area should be estimated?", "description": "Enter the combined indoor area that requires RF coverage.", "type": "text", "default": "100000"},
    {"key": "number_of_floors", "label": "Number of Floors", "prompt": "How many floors should be included in the estimate?", "description": "Record how many floors are included in the stated total coverage area.", "type": "text", "default": "1"},
    {"key": "Building_type", "label": "General Building Type", "prompt": "What general building type best describes the site?", "description": "Select the broad venue class used to load building and RF assumptions.", "type": "select", "options": building_type_options},
    {"key": "Building_category", "label": "Building Category", "prompt": "Which building category best matches the floorplan?", "description": "Refine the venue profile used to select structure and clutter assumptions.", "type": "select", "options": []},
    {"key": "use_case_type", "label": "Use Case Type", "prompt": "What is the main design intent?", "description": "For DOT architectures, Coverage Focused uses 7 DOTs per IRU; Capacity Focused uses 5.5.", "type": "select", "options": ["Coverage Focused", "Capacity Focused"]},
    {"key": "sol_type", "label": "Equipment Type", "prompt": "Which equipment architecture should the ROM assume?", "description": "Choose the radio architecture used to filter compatible radio models and BOM equipment.", "type": "select", "options": ["DOT-IRU-BBU", "Micro-BBU"]},
    {"key": "Operator_type", "label": "Operator Type", "prompt": "What operator or deployment model applies?", "description": "Select the deployment type used to determine available radios, bands, and technology.", "type": "select", "options": ["Enterprise Private 5G", "Enterprise 5G Coverage"]},
    {"key": "Coverage_type", "label": "Coverage Type", "prompt": "Which coverage technology should be calculated?", "description": "Choose whether the public-coverage estimate uses LTE (4G) or NR (5G).", "type": "select", "options": ["4G", "5G"]},
    {"key": "target_rsrp", "label": "Target RSRP (Recommended at -95 for standard EP5G designs)", "prompt": "What target RSRP should the private 5G design use?", "description": "Set the minimum design RSRP target used by the private 5G MAPL calculation.", "type": "range_slider", "default": -95, "min": -120, "max": -80, "step": 1},
    {"key": "dot_type", "label": "Radio Model", "prompt": "Which indoor radio model should be assumed?", "description": "Select the radio whose reference transmit power and antenna gain feed the MAPL.", "type": "select", "options": get_radio_dot_models()},
    {"key": "dot_variant_kry", "label": "Hardware Variant", "prompt": "Which hardware variant applies?", "description": "Choose the hardware variant that supports the required band and RF characteristics.", "type": "select", "options": []},
    {"key": "Limit_freq_type", "label": "Highest Frequency Band", "prompt": "What is the highest limiting frequency band?", "description": "Select the operating band whose center frequency is used by the coverage model.", "type": "select", "options": ["B25", "B66", "B41", "B41K", "B48", "B77G", "B77D"]},
    {"key": "Operator_count", "label": "Operators on Highest Band", "prompt": "How many operators use the highest frequency band?", "description": "Radio power per branch is split equally when more than one operator uses this band.", "type": "slider", "options": [1, 2, 3]},
    {"key": "Max_lim_channel_count", "label": "Max Channels on Highest Band", "prompt": "What is the max number of highest-band channels for one operator?", "description": "Fixed to one channel for the current ROM model.", "type": "slider", "options": [1], "hidden": True},
    {"key": "power_sharing", "label": "Power Sharing", "prompt": "Is power shared between multiple operators?", "description": "Derived automatically from the number of operators on the highest band.", "type": "checkbox", "default": False, "hidden": True},
]

def compatible_dot_variant_options(intake_data):
    dot_model = str(intake_data.get("dot_type", "")).strip()
    if not dot_model:
        return []
    technology = _intake_technology(intake_data)
    allowed_bands = _deployment_allowed_bands(intake_data)
    try:
        variants = get_radio_dot_variants(dot_model, technology=technology)
        return [
            variant
            for variant in variants
            if set(get_supported_bands(dot_model, variant, technology)).intersection(allowed_bands)
        ]
    except ValueError:
        return []


def format_dot_variant_option(variant, intake_data):
    dot_model = intake_data.get("dot_type", "")
    technology = _intake_technology(intake_data)
    allowed_bands = _deployment_allowed_bands(intake_data)
    try:
        supported_bands = sorted(
            set(get_supported_bands(dot_model, variant, technology)).intersection(allowed_bands)
        )
    except ValueError:
        supported_bands = []
    band_text = ", ".join(supported_bands) if supported_bands else "band unavailable"
    return f"{variant} ({band_text})"


def should_auto_fill_step(step, intake_data):
    operator_type = intake_data.get("Operator_type")
    if step.get("hidden", False):
        return True
    if step["key"] == "dot_variant_kry":
        radio_model = str(intake_data.get("dot_type", "")).strip()
        return bool(radio_model) and len(compatible_dot_variant_options(intake_data)) == 1
    return (
        (step["key"] == "Operator_count" and operator_type == "Enterprise Private 5G")
        or (step["key"] == "target_rsrp" and operator_type == "Enterprise 5G Coverage")
        or (step["key"] == "Coverage_type" and operator_type != "Enterprise 5G Coverage")
    )

def visible_step_indices(intake_data):
    return [
        index
        for index, step in enumerate(intake_steps)
        if not should_auto_fill_step(step, intake_data)
    ]


def visible_progress_state(current_index, intake_data):
    visible_indices = visible_step_indices(intake_data)
    visible_total = len(visible_indices)
    visible_completed = sum(
        1
        for index in visible_indices
        if intake_steps[index]["key"] in intake_data
    )
    if current_index in visible_indices:
        visible_current = visible_indices.index(current_index) + 1
    else:
        visible_current = min(visible_completed + 1, visible_total)
    return visible_current, visible_completed, visible_total


def previous_visible_step_index(current_index, intake_data):
    previous_index = max(current_index - 1, 0)
    while previous_index > 0 and should_auto_fill_step(intake_steps[previous_index], intake_data):
        previous_index -= 1
    return previous_index


def _intake_technology(intake_data):
    try:
        return resolve_technology(
            intake_data.get("Operator_type", ""),
            intake_data.get("Coverage_type", "5G"),
        )
    except ValueError:
        return None


def _deployment_allowed_bands(intake_data):
    if intake_data.get("Operator_type") == "Enterprise Private 5G":
        return {"B48"}
    return {"B25", "B66", "B41", "B41K", "B77D", "B77G"}


def get_filtered_step_options(step, intake_data):
    options = step.get("options", [])

    if step["key"] == "Building_category":
        selected_building_type = intake_data.get("Building_type")
        if selected_building_type:
            category_df = building_mapping_df[
                building_mapping_df["Building_Type"] == selected_building_type
            ]
            return sorted(category_df["Category"].dropna().unique().tolist())
        return sorted(building_mapping_df["Category"].dropna().unique().tolist())

    if step["key"] == "dot_type":
        equipment_type = intake_data.get("sol_type")
        if equipment_type == "Micro-BBU":
            radio_options = [option for option in options if option.startswith("Micro Radio")]
        else:
            radio_options = [option for option in options if option.startswith("DOT")]
            operator_type = intake_data.get("Operator_type")
            if operator_type == "Enterprise Private 5G":
                radio_options = [option for option in radio_options if option == "DOT 4459"]
            elif operator_type == "Enterprise 5G Coverage":
                radio_options = [option for option in radio_options if option in {"DOT 2274", "DOT 4455"}]
        technology = _intake_technology(intake_data)
        allowed_bands = _deployment_allowed_bands(intake_data)
        compatible_options = []
        for option in radio_options:
            try:
                supported = set(get_supported_bands(option, technology=technology))
            except ValueError:
                supported = set()
            if supported.intersection(allowed_bands):
                compatible_options.append(option)
        return compatible_options

    if step["key"] == "dot_variant_kry":
        return compatible_dot_variant_options(intake_data)

    if step["key"] == "Limit_freq_type":
        dot_model = intake_data.get("dot_type", "")
        allowed = _deployment_allowed_bands(intake_data)
        if not str(dot_model).strip():
            return [band for band in options if band in allowed]
        variant = intake_data.get("dot_variant_kry")
        technology = _intake_technology(intake_data)
        supported = set(get_supported_bands(dot_model, variant, technology))
        allowed = _deployment_allowed_bands(intake_data)
        return [band for band in options if band in supported and band in allowed]
    return options


def clear_incompatible_radio_selection(intake_data):
    radio_step = next(step for step in intake_steps if step["key"] == "dot_type")
    valid_radio_options = get_filtered_step_options(radio_step, intake_data)
    if intake_data.get("dot_type") not in valid_radio_options:
        intake_data.pop("dot_type", None)
        intake_data.pop("dot_variant_kry", None)
        intake_data.pop("Limit_freq_type", None)


def synchronize_derived_intake_values(intake_data):
    try:
        operator_count = max(int(intake_data.get("Operator_count", 1)), 1)
    except (TypeError, ValueError):
        operator_count = 1
    intake_data["Max_lim_channel_count"] = 1
    intake_data["power_sharing"] = operator_count > 1


def persist_structure_area_edits(editor_key, area_values_key):
    st.session_state[area_values_key] = apply_area_percentage_edits(
        st.session_state.get(area_values_key, []),
        st.session_state.get(editor_key, {}),
    )


def clear_cached_rf_results():
    st.session_state.mapl_result = None
    st.session_state.mapl_result_df = None
    st.session_state.mapl_result_error = ""
    st.session_state.coverage_result_df = None
    st.session_state.coverage_result_error = ""

if "rf_intake_step" not in st.session_state:
    st.session_state.rf_intake_step = 0
if "rf_intake_data" not in st.session_state:
    st.session_state.rf_intake_data = {}
if "show_intake_summary" not in st.session_state:
    st.session_state.show_intake_summary = False
if "show_clutter_information" not in st.session_state:
    st.session_state.show_clutter_information = False
if "show_add_modify_clutter" not in st.session_state:
    st.session_state.show_add_modify_clutter = False
if "show_intake_editor" not in st.session_state:
    st.session_state.show_intake_editor = False
if "rf_intake_edit_mode" not in st.session_state:
    st.session_state.rf_intake_edit_mode = False

if "mapl_result" not in st.session_state:
    st.session_state.mapl_result = None
if "mapl_result_df" not in st.session_state:
    st.session_state.mapl_result_df = None
if "mapl_result_error" not in st.session_state:
    st.session_state.mapl_result_error = ""
if "coverage_result_df" not in st.session_state:
    st.session_state.coverage_result_df = None
if "coverage_result_error" not in st.session_state:
    st.session_state.coverage_result_error = ""
total_steps = len(intake_steps)
st.session_state.rf_intake_data.pop("Mobility_type", None)
synchronize_derived_intake_values(st.session_state.rf_intake_data)


def finish_saved_intake_step():
    synchronize_derived_intake_values(st.session_state.rf_intake_data)
    if st.session_state.rf_intake_edit_mode:
        missing_steps = [
            index
            for index in visible_step_indices(st.session_state.rf_intake_data)
            if intake_steps[index]["key"] not in st.session_state.rf_intake_data
        ]
        st.session_state.rf_intake_step = missing_steps[0] if missing_steps else total_steps
        st.session_state.rf_intake_edit_mode = False
    else:
        st.session_state.rf_intake_step += 1


while st.session_state.rf_intake_step < total_steps:
    auto_fill_step = intake_steps[st.session_state.rf_intake_step]
    if not should_auto_fill_step(auto_fill_step, st.session_state.rf_intake_data):
        break
    if auto_fill_step["key"] == "Max_lim_channel_count":
        st.session_state.rf_intake_data[auto_fill_step["key"]] = 1
    elif auto_fill_step["key"] == "power_sharing":
        operator_count = max(int(st.session_state.rf_intake_data.get("Operator_count", 1)), 1)
        st.session_state.rf_intake_data[auto_fill_step["key"]] = operator_count > 1
    elif auto_fill_step["key"] == "dot_variant_kry":
        compatible_variants = compatible_dot_variant_options(st.session_state.rf_intake_data)
        if len(compatible_variants) == 1:
            st.session_state.rf_intake_data[auto_fill_step["key"]] = compatible_variants[0]
        else:
            st.session_state.rf_intake_data.pop(auto_fill_step["key"], None)
    elif auto_fill_step["key"] == "target_rsrp":
        st.session_state.rf_intake_data.pop(auto_fill_step["key"], None)
    elif auto_fill_step["key"] == "Coverage_type":
        st.session_state.rf_intake_data[auto_fill_step["key"]] = "5G"
    else:
        st.session_state.rf_intake_data[auto_fill_step["key"]] = 1
    st.session_state.rf_intake_step += 1

synchronize_derived_intake_values(st.session_state.rf_intake_data)
visible_current_step, completed_steps, visible_total_steps = visible_progress_state(
    st.session_state.rf_intake_step,
    st.session_state.rf_intake_data,
)
progress_value = min(completed_steps / visible_total_steps, 1.0) if visible_total_steps else 1.0
st.progress(progress_value, text=f"RF intake progress: {completed_steps} of {visible_total_steps} completed")

st.markdown("""
<style>
.intake-question {
    border: 1px solid #d9d9d9;
    border-radius: 6px;
    padding: 1.25rem;
    margin-top: 0.75rem;
    margin-bottom: 1rem;
}
.intake-step-label {
    color: #6b7280;
    font-size: 0.9rem;
    margin-bottom: 0.35rem;
}
.intake-description {
    color: #4b5563;
    font-size: 0.9rem;
    line-height: 1.4;
    margin-top: 0.35rem;
}
</style>
""", unsafe_allow_html=True)

if st.session_state.rf_intake_step < total_steps:
    current_step = intake_steps[st.session_state.rf_intake_step].copy()
    current_step_options = get_filtered_step_options(current_step, st.session_state.rf_intake_data)
    if current_step_options:
        current_step["options"] = current_step_options
    st.markdown(
        f"""
        <div class="intake-question">
            <div class="intake-step-label">Question {visible_current_step} of {visible_total_steps}</div>
            <h3>{current_step['prompt']}</h3>
            <div class="intake-description">{current_step['description']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    existing_value = st.session_state.rf_intake_data.get(
        current_step["key"],
        current_step.get("default", current_step.get("options", [None])[0]),
    )

    is_edit_mode = st.session_state.rf_intake_edit_mode

    with st.form(key="guided_rf_solution_form"):
        if current_step["type"] == "text":
            step_value = st.text_input(current_step["label"], value=str(existing_value))
        elif current_step["type"] == "select":
            options = current_step["options"]
            selected_index = options.index(existing_value) if existing_value in options else 0
            if current_step["key"] == "dot_variant_kry" and len(options) > 1:
                step_value = st.selectbox(
                    current_step["label"],
                    options,
                    index=selected_index,
                    format_func=lambda variant: format_dot_variant_option(
                        variant,
                        st.session_state.rf_intake_data,
                    ),
                )
            else:
                step_value = st.selectbox(current_step["label"], options, index=selected_index)
        elif current_step["type"] == "slider":
            options = current_step["options"]
            selected_index = options.index(existing_value) if existing_value in options else 0
            step_value = st.select_slider(current_step["label"], options=options, value=options[selected_index])
        elif current_step["type"] == "range_slider":
            step_value = st.slider(
                current_step["label"],
                min_value=current_step["min"],
                max_value=current_step["max"],
                value=int(existing_value),
                step=current_step.get("step", 1),
            )
        else:
            step_value = st.checkbox(current_step["label"], value=bool(existing_value))

        col_back, col_next = st.columns([1, 3])
        with col_back:
            back_clicked = st.form_submit_button(
                "Cancel" if is_edit_mode else "Back",
                disabled=not is_edit_mode and st.session_state.rf_intake_step == 0,
            )
        with col_next:
            next_clicked = st.form_submit_button("Save changes" if is_edit_mode else "Save and continue")

    if back_clicked:
        if is_edit_mode:
            st.session_state.rf_intake_step = total_steps
            st.session_state.rf_intake_edit_mode = False
        else:
            st.session_state.rf_intake_step = previous_visible_step_index(
                st.session_state.rf_intake_step,
                st.session_state.rf_intake_data,
            )
        st.rerun()

    if next_clicked:
        cleaned_value = step_value
        if current_step["type"] == "text" and not str(step_value).strip():
            st.warning("Please enter a value before continuing.")
        elif current_step["key"] == "total_sqft":
            try:
                total_sqft_value = float(str(step_value).replace(",", ""))
                if total_sqft_value <= 0:
                    raise ValueError
                clear_cached_rf_results()
                st.session_state.rf_intake_data[current_step["key"]] = f"{total_sqft_value:.0f}"
                finish_saved_intake_step()
                st.rerun()
            except ValueError:
                st.warning("Please enter a positive number for total coverage area.")
        elif current_step["key"] == "number_of_floors":
            try:
                floor_count = int(str(step_value).replace(",", "").strip())
                if floor_count <= 0:
                    raise ValueError
                clear_cached_rf_results()
                st.session_state.rf_intake_data[current_step["key"]] = floor_count
                finish_saved_intake_step()
                st.rerun()
            except ValueError:
                st.warning("Please enter a positive whole number for Number of Floors.")
        else:
            if current_step["type"] == "text":
                cleaned_value = str(step_value).strip()
            clear_cached_rf_results()
            st.session_state.rf_intake_data[current_step["key"]] = cleaned_value
            if current_step["key"] == "Building_type":
                saved_category = st.session_state.rf_intake_data.get("Building_category")
                valid_category_options = get_filtered_step_options(
                    next(step for step in intake_steps if step["key"] == "Building_category"),
                    st.session_state.rf_intake_data,
                )
                if saved_category not in valid_category_options:
                    st.session_state.rf_intake_data.pop("Building_category", None)
            if current_step["key"] == "sol_type":
                clear_incompatible_radio_selection(st.session_state.rf_intake_data)
            if current_step["key"] == "dot_type":
                st.session_state.rf_intake_data.pop("dot_variant_kry", None)
                st.session_state.rf_intake_data.pop("Limit_freq_type", None)
            if current_step["key"] == "dot_variant_kry":
                st.session_state.rf_intake_data.pop("Limit_freq_type", None)
            if current_step["key"] == "Limit_freq_type":
                if (
                    st.session_state.rf_intake_data.get("Operator_type") == "Enterprise 5G Coverage"
                    and cleaned_value == "B77D"
                ):
                    st.session_state.rf_intake_data["target_rsrp"] = -100
                elif st.session_state.rf_intake_data.get("Operator_type") == "Enterprise 5G Coverage":
                    st.session_state.rf_intake_data.pop("target_rsrp", None)
            if current_step["key"] == "Operator_type":
                if cleaned_value == "Enterprise Private 5G":
                    st.session_state.rf_intake_data["Coverage_type"] = "5G"
                    st.session_state.rf_intake_data["target_rsrp"] = st.session_state.rf_intake_data.get("target_rsrp", -95)
                    st.session_state.rf_intake_data["Operator_count"] = 1
                    st.session_state.rf_intake_data["Max_lim_channel_count"] = 1
                    st.session_state.rf_intake_data["power_sharing"] = False
                else:
                    st.session_state.rf_intake_data.pop("Coverage_type", None)
                    st.session_state.rf_intake_data.pop("target_rsrp", None)
                clear_incompatible_radio_selection(st.session_state.rf_intake_data)
                saved_band = st.session_state.rf_intake_data.get("Limit_freq_type")
                valid_band_options = get_filtered_step_options(
                    next(step for step in intake_steps if step["key"] == "Limit_freq_type"),
                    st.session_state.rf_intake_data,
                )
                if saved_band not in valid_band_options:
                    st.session_state.rf_intake_data.pop("Limit_freq_type", None)
            if current_step["key"] == "Coverage_type":
                clear_incompatible_radio_selection(st.session_state.rf_intake_data)
                saved_band = st.session_state.rf_intake_data.get("Limit_freq_type")
                valid_band_options = get_filtered_step_options(
                    next(step for step in intake_steps if step["key"] == "Limit_freq_type"),
                    st.session_state.rf_intake_data,
                )
                if saved_band not in valid_band_options:
                    st.session_state.rf_intake_data.pop("Limit_freq_type", None)
            if current_step["key"] == "Operator_count":
                synchronize_derived_intake_values(st.session_state.rf_intake_data)
            finish_saved_intake_step()
            st.rerun()
else:
    st.success("RF solution intake complete. You can review, modify, or reset the intake below.")
    modify_col, reset_col, summary_toggle_col = st.columns([1, 1, 1])
    with modify_col:
        if st.button("Modify intake"):
            st.session_state.show_intake_editor = not st.session_state.show_intake_editor
            st.session_state.pop("rf_intake_edit_field", None)
            st.rerun()
    with reset_col:
        if st.button("Reset RF intake"):
            st.session_state.rf_intake_step = 0
            st.session_state.rf_intake_data = {}
            st.session_state.rf_intake_edit_mode = False
            st.session_state.show_intake_editor = False
            st.session_state.pop("rf_intake_edit_field", None)
            st.session_state.show_intake_summary = False
            st.session_state.show_clutter_information = False
            st.session_state.show_add_modify_clutter = False
            st.session_state.mapl_result = None
            st.session_state.mapl_result_df = None
            st.session_state.mapl_result_error = ""
            st.session_state.coverage_result_df = None
            st.session_state.coverage_result_error = ""
            st.session_state.pop("coverage_design_margin_db", None)
            st.rerun()
    with summary_toggle_col:
        if st.button("Show/Hide Intake Summary"):
            st.session_state.show_intake_summary = not st.session_state.show_intake_summary
            st.rerun()

    if st.session_state.show_intake_editor:
        editable_indices = visible_step_indices(st.session_state.rf_intake_data)
        selected_edit_index = st.selectbox(
            "Select an intake field to modify",
            editable_indices,
            format_func=lambda index: (
                f"{intake_steps[index]['label']}: "
                f"{st.session_state.rf_intake_data.get(intake_steps[index]['key'], 'Not entered')}"
            ),
            key="rf_intake_edit_field",
        )
        if st.button("Edit selected field"):
            st.session_state.rf_intake_step = selected_edit_index
            st.session_state.rf_intake_edit_mode = True
            st.session_state.show_intake_editor = False
            st.rerun()
location_summary_rows = [
    {"Field": "Address", "Value": address_query.strip() or st.session_state.selected_address or "Not provided"},
    {"Field": "Latitude", "Value": f"{st.session_state.location_latitude:.6f}"},
    {"Field": "Longitude", "Value": f"{st.session_state.location_longitude:.6f}"},
]

summary_rows = location_summary_rows + [
    {"Field": step["label"], "Value": st.session_state.rf_intake_data[step["key"]]}
    for step in intake_steps
    if step["key"] in st.session_state.rf_intake_data and not step.get("hidden", False)
]

if st.session_state.show_intake_summary:
    st.subheader("RF Intake Summary")
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        st.markdown("""
        <style>
        .rf-summary-table {
            display: inline-block;
            max-width: 100%;
            overflow-x: auto;
        }
        .rf-summary-table table {
            width: auto;
            border-collapse: collapse;
        }
        .rf-summary-table th,
        .rf-summary-table td {
            border-bottom: 1px solid #e5e7eb;
            padding: 0.45rem 0.85rem;
            text-align: left;
            white-space: nowrap;
        }
        .rf-summary-table th {
            font-weight: 700;
        }
        </style>
        """, unsafe_allow_html=True)
        st.markdown(
            f"<div class='rf-summary-table'>{summary_df.to_html(index=False, escape=True)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("Completed answers will appear here as the intake progresses.")

if st.session_state.rf_intake_step >= total_steps:
    selected_building_type = st.session_state.rf_intake_data.get("Building_type")
    selected_building_category = st.session_state.rf_intake_data.get("Building_category")
    structure_columns = [
        "Building_Type",
        "Category",
        "Sub_Type_A",
        "Sub_Type_Area_%",
        "RF_Floorplan_Match_Notes",
    ]

    if st.button("Show/Hide Clutter Information"):
        st.session_state.show_clutter_information = not st.session_state.show_clutter_information
        if not st.session_state.show_clutter_information:
            st.session_state.show_add_modify_clutter = False
        st.rerun()

    if selected_building_type and selected_building_category:
        selected_structure_df = building_mapping_df[
            (building_mapping_df["Building_Type"] == selected_building_type)
            & (building_mapping_df["Category"] == selected_building_category)
        ][structure_columns].copy()

        extra_rows_key = f"structure_extra_rows::{selected_building_type}::{selected_building_category}"
        if extra_rows_key not in st.session_state:
            st.session_state[extra_rows_key] = pd.DataFrame(columns=structure_columns)

        display_structure_df = pd.concat(
            [selected_structure_df, st.session_state[extra_rows_key]],
            ignore_index=True,
        )

        structure_table_key = f"structure_area_table_{selected_building_type}_{selected_building_category}"
        structure_area_values_key = f"structure_area_values::{selected_building_type}::{selected_building_category}"
        base_area_pct_values = pd.to_numeric(
            display_structure_df["Sub_Type_Area_%"],
            errors="coerce",
        ).fillna(0).tolist()
        st.session_state[structure_area_values_key] = reconcile_area_percentages(
            base_area_pct_values,
            st.session_state.get(structure_area_values_key),
        )
        edited_structure_df = display_structure_df.copy()
        edited_structure_df["Sub_Type_Area_%"] = st.session_state[structure_area_values_key]

        try:
            total_coverage_sqft = float(str(st.session_state.rf_intake_data.get("total_sqft", "0")).replace(",", ""))
        except ValueError:
            total_coverage_sqft = 0.0
        area_pct_values = pd.to_numeric(edited_structure_df["Sub_Type_Area_%"], errors="coerce").fillna(0)
        edited_structure_df["Coverage Area"] = (total_coverage_sqft * area_pct_values / 100).round(0).astype(int)
        visible_structure_columns = ["Building_Type", "Category", "Sub_Type_A", "Sub_Type_Area_%", "Coverage Area"]

        if st.session_state.show_clutter_information:
            st.subheader("Building and Clutter Information")
            if display_structure_df.empty:
                st.caption("No building and clutter rows found for the selected structure.")
            else:
                edited_visible_structure_df = st.data_editor(
                    edited_structure_df[visible_structure_columns],
                    width="stretch",
                    hide_index=True,
                    disabled=["Building_Type", "Category", "Sub_Type_A", "Coverage Area"],
                    column_config={
                        "Building_Type": st.column_config.TextColumn(
                            "Building Type",
                            width="small",
                        ),
                        "Category": st.column_config.TextColumn(
                            "Category",
                            width="small",
                        ),
                        "Sub_Type_A": st.column_config.TextColumn(
                            "Sub Type",
                            width="medium",
                        ),
                        "Sub_Type_Area_%": st.column_config.NumberColumn(
                            "Area %",
                            min_value=0.0,
                            max_value=100.0,
                            step=1.0,
                            width="small",
                        ),
                        "Coverage Area": st.column_config.NumberColumn(
                            "Coverage Area",
                            format="%d sq ft",
                            width="small",
                        ),
                    },
                    key=structure_table_key,
                    on_change=persist_structure_area_edits,
                    args=(structure_table_key, structure_area_values_key),
                )
                edited_area_values = reconcile_area_percentages(
                    base_area_pct_values,
                    edited_visible_structure_df["Sub_Type_Area_%"].tolist(),
                )
                st.session_state[structure_area_values_key] = edited_area_values
                edited_structure_df["Sub_Type_Area_%"] = edited_area_values
                edited_area_pct_values = pd.to_numeric(edited_structure_df["Sub_Type_Area_%"], errors="coerce").fillna(0)
                edited_structure_df["Coverage Area"] = (total_coverage_sqft * edited_area_pct_values / 100).round(0).astype(int)
                st.caption("Coverage Area is calculated from Total Sq.Ft Coverage and each Sub Type Area %. Hover over the info icons beside each Sub Type A to view RF floorplan match notes.")
                st.markdown(
                    render_structure_note_tooltips(edited_structure_df),
                    unsafe_allow_html=True,
                )
                if st.button("Add/Modify Clutter"):
                    st.session_state.show_add_modify_clutter = not st.session_state.show_add_modify_clutter
                    st.rerun()
                area_total = pd.to_numeric(edited_structure_df["Sub_Type_Area_%"], errors="coerce").fillna(0).sum()
                if abs(area_total - 100.0) > 0.01:
                    st.warning(f"Sub Type Area % currently totals {area_total:.1f}%. Please update the percentage area to 100%.")

            if st.session_state.show_add_modify_clutter:
                available_sub_types_df = building_mapping_df
                sub_type_a_options = sorted(available_sub_types_df["Sub_Type_A"].dropna().astype(str).str.strip().unique().tolist())

                with st.form("add_structure_detail_row", clear_on_submit=True):
                    st.caption("Add another structure detail row")
                    if sub_type_a_options:
                        new_sub_type = st.selectbox("Sub Type A", sub_type_a_options)
                    else:
                        new_sub_type = st.text_input("Sub Type A")
                    new_area_pct = st.number_input("Sub Type Area %", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                    selected_note_rows = available_sub_types_df[
                        available_sub_types_df["Sub_Type_A"].astype(str).str.strip() == str(new_sub_type).strip()
                    ]
                    default_floorplan_note = ""
                    if not selected_note_rows.empty:
                        default_floorplan_note = str(selected_note_rows.iloc[0].get("RF_Floorplan_Match_Notes", ""))
                    new_floorplan_notes = st.text_area("RF Floorplan Match Notes", value=default_floorplan_note)
                    add_structure_row = st.form_submit_button("Add structure row")

                if add_structure_row:
                    if not str(new_sub_type).strip():
                        st.warning("Please select a Sub Type A value before adding the row.")
                    else:
                        new_structure_row = pd.DataFrame([{
                            "Building_Type": selected_building_type,
                            "Category": selected_building_category,
                            "Sub_Type_A": str(new_sub_type).strip(),
                            "Sub_Type_Area_%": new_area_pct,
                            "RF_Floorplan_Match_Notes": new_floorplan_notes.strip(),
                        }])
                        st.session_state[extra_rows_key] = pd.concat(
                            [st.session_state[extra_rows_key], new_structure_row],
                            ignore_index=True,
                        )
                        updated_area_total = pd.to_numeric(
                            pd.concat([edited_structure_df, new_structure_row], ignore_index=True)["Sub_Type_Area_%"],
                            errors="coerce",
                        ).fillna(0).sum()
                        if abs(updated_area_total - 100.0) > 0.01:
                            st.warning(f"Sub Type Area % now totals {updated_area_total:.1f}%. Please update the percentage area to 100%.")
                        else:
                            st.success("Structure row added.")
                        st.rerun()
        show_rf_details_key = f"show_rf_details::{selected_building_type}::{selected_building_category}"
        rf_details_button = st.button("Show/Hide Building RF/Structural Details")
        if rf_details_button:
            st.session_state[show_rf_details_key] = not st.session_state.get(show_rf_details_key, False)
            st.rerun()
        rf_detail_columns = [
            "Sub_Type_A",
            "Coverage Area",
            "Concrete_%",
            "Drywall_%",
            "Glass_%",
            "Metal_%",
            "Open_Area_%",
            "Light_Clutter_%",
            "Medium_Clutter_%",
            "Dense_Clutter_%",
            "Ceiling_Height_Class",
            "Environment_Type",
            "Layout_Complexity",
            "Total Losses Material",
            "Total Loss Density",
            "Total Loss",
        ]
        rf_assumption_columns = [column for column in rf_detail_columns if column != "Coverage Area"]
        rf_engine_assumption_columns = rf_assumption_columns + ["Assumption_Profile", "Assumption_Basis"]
        rf_details_df = edited_structure_df[["Sub_Type_A", "Coverage Area"]].merge(
            unique_assumption_df[rf_engine_assumption_columns].drop_duplicates(subset=["Sub_Type_A"]),
            on="Sub_Type_A",
            how="left",
        )
        rf_engine_df = rf_details_df.copy()
        rf_engine_df["Area_ID"] = [f"area-{index + 1}" for index in range(len(rf_engine_df))]
        rf_engine_df["Building_Name"] = st.session_state.rf_intake_data.get("venue_name", "")
        rf_engine_df["Building_Type"] = selected_building_type
        rf_engine_df["Category"] = selected_building_category
        rf_engine_df["Band"] = st.session_state.rf_intake_data.get("Limit_freq_type", "")

        if st.session_state.get(show_rf_details_key, False):
            st.subheader("Building RF/Structural Details")
            st.dataframe(
                rf_details_df[rf_detail_columns],
                width="content",
                hide_index=True,
            )

        intake_data = st.session_state.rf_intake_data
        margin_db = resolve_streamlit_design_margin_db(
            intake_data.get("Operator_type", "")
        )
        selected_radio_characteristics = None
        selected_radio_error = ""
        try:
            selected_technology = resolve_technology(
                intake_data.get("Operator_type", ""),
                intake_data.get("Coverage_type", "5G"),
            )
            selected_radio_characteristics = get_radio_dot_characteristics(
                dot_model=intake_data.get("dot_type", ""),
                dot_variant_kry=intake_data.get("dot_variant_kry"),
                band=intake_data.get("Limit_freq_type", ""),
                technology=selected_technology,
            )
        except ValueError as error:
            selected_radio_error = str(error)

        carrier_frequency_override = None
        configured_tx_power_override = None
        operator_count = max(int(intake_data.get("Operator_count", 1)), 1)
        power_is_total_across_carriers = operator_count > 1
        if selected_radio_characteristics is None and selected_radio_error:
            st.error(selected_radio_error)

        coverage_overrides = {}

        if st.button("Run RF calculations"):
            intake_data = st.session_state.rf_intake_data
            target_rsrp_dbm = float(intake_data.get("target_rsrp", -95))
            try:
                technology = resolve_technology(
                    intake_data.get("Operator_type", ""),
                    intake_data.get("Coverage_type", "5G"),
                )
                if selected_radio_characteristics is None:
                    raise ValueError(selected_radio_error or "Select a supported radio configuration.")
                radio_inputs = dict(intake_data)
                radio_inputs.update({
                    "technology": technology,
                    "target_rsrp_dbm": target_rsrp_dbm,
                    "margin_db": margin_db,
                    "carrier_count": 1,
                    "power_share_count": operator_count,
                    "power_is_total_across_carriers": power_is_total_across_carriers,
                })
                if carrier_frequency_override is not None:
                    radio_inputs["carrier_frequency_mhz"] = carrier_frequency_override
                if configured_tx_power_override is not None:
                    radio_inputs["configured_tx_power_dbm_per_branch"] = configured_tx_power_override
                calculated_defaults = {
                    "technology": technology,
                    "bandwidth_mhz": default_bandwidth_mhz(
                        selected_radio_characteristics.band,
                        technology,
                    ),
                    "scs_khz": 30 if technology == "NR" else None,
                    "margin_db": margin_db,
                }
                radio_config = build_radio_mapl_config(
                    user_inputs=radio_inputs,
                    calculated_data=calculated_defaults,
                    radio_reference=selected_radio_characteristics,
                )
                mapl_result = calculate_mapl(radio_config)
                coverage_result_df = calculate_coverage_for_all_buildings(
                    rf_engine_df,
                    [mapl_result],
                    margin_db=margin_db,
                    overrides=coverage_overrides,
                )
                st.session_state.mapl_result = mapl_result
                st.session_state.mapl_result_df = mapl_result_to_table(mapl_result)
                st.session_state.coverage_result_df = coverage_result_df
                st.session_state.mapl_result_error = ""
                st.session_state.coverage_result_error = ""
            except Exception as error:
                st.session_state.mapl_result = None
                st.session_state.mapl_result_df = None
                st.session_state.coverage_result_df = None
                st.session_state.mapl_result_error = str(error)
                st.session_state.coverage_result_error = ""
            st.rerun()
        if st.session_state.get("mapl_result_error"):
            st.error(st.session_state.mapl_result_error)

        if st.session_state.get("coverage_result_error"):
            st.error(st.session_state.coverage_result_error)
        if st.session_state.get("coverage_result_df") is not None:
            coverage_result_df = st.session_state.coverage_result_df
            result_technology = st.session_state.mapl_result.get("Technology", "") if st.session_state.mapl_result else ""
            st.subheader(f"Step 2 - {result_technology} Coverage Results")
            dots_per_iru = 5.5 if intake_data.get("use_case_type") == "Capacity Focused" else 7.0
            equipment_summary = summarize_building_equipment(
                coverage_result_df,
                dots_per_iru=dots_per_iru,
            )
            if equipment_summary["Total_Required_DOTs_Radios"] > 0:
                selected_model = str(st.session_state.mapl_result.get("Dot_Model", ""))
                if selected_model.startswith("Micro Radio"):
                    average_col, radio_col = st.columns(2)
                    average_col.metric(
                        "Average sq ft / Micro Radio",
                        f"{equipment_summary['Average_sqft_per_DOT_Radio']:,.0f}",
                    )
                    radio_col.metric(
                        "Total required Micro Radios",
                        f"{equipment_summary['Total_Required_DOTs_Radios']:,}",
                    )
                    st.caption(
                        "Micro Radio count is coverage based. IRU and BBU quantities are not shown because "
                        "the reference table does not define a Micro Radio-to-baseband equipment ratio."
                    )
                else:
                    average_col, dot_col, iru_col, bbu_col = st.columns(4)
                    average_col.metric(
                        "Average sq ft / DOT",
                        f"{equipment_summary['Average_sqft_per_DOT_Radio']:,.0f}",
                    )
                    dot_col.metric(
                        "Total required DOTs/Radios",
                        f"{equipment_summary['Total_Required_DOTs_Radios']:,}",
                    )
                    iru_col.metric("Total IRUs", f"{equipment_summary['Total_IRUs']:,}")
                    bbu_col.metric("Total BBUs", f"{equipment_summary['Total_BBUs']:,}")
                    st.caption(
                        "Average sq ft / DOT equals total modeled building area divided by total required radios. "
                        f"IRUs are rounded up at {dots_per_iru:g} DOTs/Radios per IRU for the selected use case; "
                        "BBUs are rounded up at 12 IRUs per BBU."
                    )
            else:
                st.warning("No model-valid building equipment summary is available for these results.")


    else:
        st.caption("Select General Building Type and Building Category to view the associated structure details.")
