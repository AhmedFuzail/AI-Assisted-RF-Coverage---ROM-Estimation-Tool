import streamlit as st
import os
import pandas as pd

st.set_page_config(
    page_title="Ericsson RF ROM Tool",
    page_icon="static/Ericsson_icon.png"   # your image file
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
#header_Main = st.header("DOT 4459")
st.divider()
subheader_Main = st.subheader("Pre-Sales Support Tool For Quick HW estimation for EP5G Deployments")
#markdown_Main = st.markdown("This is the ##**_test version_**##")
#st.divider()
caption_main = st.caption("E/// Internal Only")

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

Loc_data = {
    "latitude": [37.493544],
    "longitude": [-121.945242],
}

df_Loc = pd.DataFrame(Loc_data)
edit_df = st.data_editor(df_Loc, width='content')
map_loc= st.map(edit_df, size=75, zoom=14.5, height= 225)
print(edit_df)

st.divider()
markdown_Main = st.header("User Intake Section")
#st.divider()
caption_main = st.caption("Solution and RF details", )

with st.form(key ='rf_solution_form'):
    Customer_name = st.text_input("Enter Customer Name")
    venue_name = st.text_input("Enter Venue Name")
    total_sqft = st.text_input("Enter Total Sq.Ft Coverage", value=100000)
    Building_type = st.selectbox(
                "Select General Building Type",
                ["Office", "Industrial","Healthcare", "Education","Retail", "Hospitality","Transportation", "Data_Center","Hospitality","Residential", "Mixed_Use","Parking_Garage"])   
    use_case_type = st.selectbox(
                "Select Use Case type",
                ["Coverage_Focused", "Balanced","Capacity_Focused", "High_Capacity_Critical"])
    sol_type = st.selectbox(
                "Select Equipment type",
                ["DOT-IRU-BBU", "Micro-BBU"])
    Operator_type = st.selectbox(
                "Select Operator Type",
                ["Private_4G", "EP5G","Single_MNO", "Neutral_Host"])
    Mobility_type = st.selectbox(
                "Select Mobility Requirments for Use Case",
                ["Static", "Low_Mobility","Moderate_Mobility", "High_Mobility"])
    dot_type = st.selectbox(
                "Select DOT/Radio type",
                ["RD4459", "Micro_4408","Micro_4402", "RD4455", "RD2274"])
    Limit_freq_type = st.selectbox(
                "Highest Frequency Band",
                ["B48-CBRS", "B2/B25","B4/B66", "N77/C-Band"])
    Operator_count = st.select_slider(
                "Number of Operators using Highest Frequency Band",
                options=[1,2,3])
    Max_lim_channel_count = st.select_slider(
                "Max Number of channels of the Highest Frequency Band for an operator",
                options=[1,2,3])
    power_sharing = st.checkbox(
                "Power Sharing Between Multiple Operators",
                value= False)
    caption_Submit_RF = st.caption("Submit and Move to Building Details")
    Submit_button = st.form_submit_button(label="Submit", )


# -----------------------------
# Dropdown options
# -----------------------------


sub_type_options = [
    "Open_Office", "Cubicle_Office", "High_Density_Office", "Executive_Office",
    "Office_With_Lab", "Office_With_Warehouse", "Call_Center", "R&D_Office",
    "Heavy_Manufacturing", "Light_Manufacturing", "Assembly_Line", "Warehouse",
    "Distribution_Center", "Automotive_Production", "Semiconductor_Fab",
    "Clean_Room_Production", "Utility_Plant", "Workshop", "General_Hospital",
    "Specialty_Hospital", "Clinic", "Imaging_Center", "Medical_Lab",
    "Surgical_Center", "Pharmacy_Facility", "School", "University_Academic",
    "Research_Lab", "Library", "Auditorium", "Student_Center", "Sports_Facility",
    "Mall", "Big_Box_Retail", "Grocery_Store", "Small_Retail", "Restaurant",
    "Food_Court", "Showroom", "Hotel", "Resort", "Convention_Center",
    "Banquet_Hall", "Conference_Facility", "Airport_Terminal", "Train_Station",
    "Bus_Terminal", "Port_Facility", "Parking_Garage", "Logistics_Hub",
    "Server_Room", "Enterprise_Data_Center", "Hyperscale_Data_Center",
    "Telecom_Room", "MDF_IDF_Facility", "Single_Family", "Apartment",
    "Condominium", "High_Rise_Residential", "Dormitory", "Office_Retail_Mix",
    "Office_Lab_Mix", "Residential_Retail_Mix", "Industrial_Office_Mix",
    "Campus_Mix", "Stadium", "Arena", "Museum", "Worship_Facility",
    "Government_Building", "Community_Center", "Exhibition_Hall"
]

construction_type_options = [
    "Light_Drywall", "Glass_Dominant", "Brick_Masonry", "Concrete_Standard",
    "Reinforced_Concrete", "Metal_Frame", "Metal_Dense", "Precast_Concrete",
    "Industrial_Steel", "Mixed_Material"
]

clutter_profile_options = [
    "Wide_Open", "Light_Clutter", "Medium_Clutter",
    "Dense_Clutter", "Very_Dense_Clutter"
]

ceiling_height_options = [
    "Low_8_12ft", "Medium_12_18ft", "High_18_30ft", "Very_High_30ft_plus"
]

percentage_options = [
    100,90,70,50,35,15,10
]

# -----------------------------
# Session state table storage
# -----------------------------
if "form_data_table" not in st.session_state:
    st.session_state.form_data_table = pd.DataFrame(columns=[
        "Sub Type (All)",
        "Construction Type",
        "Clutter Profile",
        "Ceiling Height Class",
        "Percentage Area"
    ])

with st.form("building_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        sub_type = st.selectbox("Sub Type (All)", sub_type_options)
        construction_type = st.selectbox("Construction Type", construction_type_options)
        area_percentage = st.selectbox("Percentage Contribution to Total Area", percentage_options)


    with col2:
        clutter_profile = st.selectbox("Clutter Profile", clutter_profile_options)
        ceiling_height = st.selectbox("Ceiling Height Class", ceiling_height_options)

    submitted = st.form_submit_button("Add Row")

if submitted:
    new_row = pd.DataFrame([{
        "Sub Type (All)": sub_type,
        "Construction Type": construction_type,
        "Clutter Profile": clutter_profile,
        "Ceiling Height Class": ceiling_height,
        "Percentage Area": area_percentage
    }])

    st.session_state.form_data_table = pd.concat(
        [st.session_state.form_data_table, new_row],
        ignore_index=True
    )

    st.success("New row added successfully.")

# -----------------------------
# Show table at bottom
# -----------------------------
st.subheader("Submitted Data")
st.dataframe(st.session_state.form_data_table, width='content')

# Optional download button
if not st.session_state.form_data_table.empty:
    csv = st.session_state.form_data_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Table as CSV",
        data=csv,
        file_name="building_category_data.csv",
        mime="text/csv"
    )

import random

base = 16400

# random number in thousands (1000 to 9000)
rand_thousands = random.randint(1, 9) * 250

# randomly add or subtract
result = base + rand_thousands if random.choice([True, False]) else base - rand_thousands

st.divider()

st.text("(THESE ARE NOT ACTUALL RESULTS (DEMO ONLY)")
 
st.markdown("""
<style>
.custom-textbox {
    border: 4px solid #4CAF50;
    border-radius: 8px;
    padding: 10px;
    font-size: 22px;
    width: auto !important;
}
</style>
""", unsafe_allow_html=True)

user_input = f"{result:,.2f}"
if submitted or Submit_button: 
    st.text("Coverage per DOT in  sq . ft")
    st.markdown(f"""
    <input class="custom-textbox" value="{user_input}">
    """, unsafe_allow_html=True)
    total_dots = float(total_sqft) / float(result)
    total_dots_rounded = (round(total_dots,0))
    st.write("\n")
    st.text("Required DOTs")
    st.markdown(f"""
    <input class="custom-textbox" value="{total_dots_rounded}">
    """, unsafe_allow_html=True)
    st.write("\n")
    total_IRUs = total_dots_rounded / 7
    total_IRUs_rounded = round(total_IRUs,0)
    st.text("Required IRUs")
    st.markdown(f"""
    <input class="custom-textbox" value="{total_IRUs_rounded}">
    """, unsafe_allow_html=True)

