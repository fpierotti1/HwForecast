import streamlit as st
import pandas as pd
import itertools
import os
import sys
import json
from fpdf import FPDF
import base64
import platform
import math

# Page Config
st.set_page_config(
    page_title="Laptop Forecast App v3.5",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- V2.0 DESKTOP HELPERS ---
def get_app_dir():
    """Returns the directory of the application (Supports PyInstaller & Script)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled .exe
        return os.path.dirname(sys.executable)
    else:
        # Running as .py script
        return os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    return os.path.join(get_app_dir(), "settings.json")

def load_config():
    config_path = get_config_path()
    default_config = {"database_path": "forecast_db.json"}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except:
            return default_config
    return default_config

def save_config(config):
    with open(get_config_path(), "w") as f:
        json.dump(config, f, indent=4)

def get_db_path():
    config = load_config()
    db_path = config.get("database_path", "forecast_db.json")
    
    # Check if path is empty
    if not db_path:
        db_path = "forecast_db.json"
        
    # Formatting: Remove potential quotes from Windows "Copy as path"
    db_path = db_path.strip().strip('"')
    
    # Return directly. Let OS resolve relation to CWD.
    return db_path

# --- Dimensions ---
MODELS = ["Apple MacBook 14\"", "Apple MacBook 16\"", "Microsoft SL7"]
REGIONS = ["EMEA", "UK", "Tel Aviv", "LATAM", "NAMER", "APAC"]
ALL_LANGS = ["English", "French", "German", "Hebrew", "Italian", "Spanish", "Swedish"]

# --- HELPER FUNCTIONS ---

def get_previous_quarter_name(quarter_str):
    """
    Parses 'FYXX QY' and returns the previous quarter.
    E.g. FY27 Q1 -> FY26 Q4
    """
    try:
        parts = quarter_str.split()
        fy_part = parts[0] # FY27
        q_part = parts[1]  # Q1
        
        fy_year = int(fy_part.replace("FY", ""))
        q_num = int(q_part.replace("Q", ""))
        
        prev_q_num = q_num - 1
        prev_fy_year = fy_year
        
        if prev_q_num < 1:
            prev_q_num = 4
            prev_fy_year -= 1
            
        return f"FY{prev_fy_year} Q{prev_q_num}"
    except:
        return None

def process_stock_upload(uploaded_file):
    try:
        try:
            df_upload = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            # Fallback for Excel-generated CSVs (often cp1252/latin1)
            uploaded_file.seek(0)
            df_upload = pd.read_csv(uploaded_file, encoding='ISO-8859-1')
        
        # 1. Normalize Columns (Handle variations)
        # Ensure we have the right columns or rename them
        if 'model.short_description' not in df_upload.columns:
            return 0, "Error: Column 'model.short_description' not found."
            
        # 2. Map Models
        def map_model(desc):
            s = str(desc).lower()
            if "14\"" in s and ("macbook" in s or "pro" in s or "air" in s): return "Apple MacBook 14\""
            if "16\"" in s and ("macbook" in s or "pro" in s): return "Apple MacBook 16\""
            if "surface" in s or "laptop" in s or "studio" in s: return "Microsoft SL7"
            return None # Skip others

        # 3. Map Regions (Updated v3.3)
        def map_region(row):
            loc = str(row.get('location', '')).upper()
            geo = str(row.get('location.u_geographic_region', '')).upper()
            
            # Precise Location Overrides
            if "MLN8" in loc: return "UK"       # New Rule
            if "LSP3" in loc: return "LATAM"    # New Rule
            if "LMX1" in loc or "LSNX" in loc: return "NAMER"
            if "MTV" in loc: return "Tel Aviv"
            
            # Geographic Region Fallbacks
            if "AMER" in geo: return "NAMER"
            if "APAC" in geo: return "APAC"
            if "EMEA" in geo: return "EMEA"
            
            return "EMEA" # Default fallback

        # 4. Map Languages
        def map_language(lang):
            l = str(lang).title()
            if "English" in l: return "English"
            return l

        df_upload['App_Model'] = df_upload['model.short_description'].apply(map_model)
        df_upload['App_Region'] = df_upload.apply(map_region, axis=1)
        df_upload['App_Language'] = df_upload['model.ref_cmdb_hardware_product_model.u_keyboard_language'].apply(map_language)

        # 5. Aggregate Counts
        stock_counts = df_upload.groupby(['App_Region', 'App_Model', 'App_Language']).size().reset_index(name='New_Stock')
        
        # 6. Merge into Session State
        # Iterate and update specific rows in st.session_state.data_df
        count_updated = 0
        for _, row in stock_counts.iterrows():
            mask = (
                (st.session_state.data_df['Region'] == row['App_Region']) & 
                (st.session_state.data_df['Model'] == row['App_Model']) & 
                (st.session_state.data_df['Language'] == row['App_Language'])
            )
            if mask.any():
                st.session_state.data_df.loc[mask, 'Physical Stock (Input)'] = row['New_Stock']
                count_updated += 1
                
        return count_updated, None
    except Exception as e:
        return 0, str(e)

def get_languages_for_region(region):
    """Enforce Regional Constraints."""
    if region == "UK":
        return ["English"]
    elif region == "Tel Aviv":
        return ["Hebrew"]
    elif region == "NAMER":
        return ["English"]
    elif region == "APAC":
        return ["English"]
    elif region == "LATAM":
        return ["English"]
    elif region == "EMEA":
        # EMEA = All except Hebrew
        return [l for l in ALL_LANGS if l != "Hebrew"]
    else:
        return ALL_LANGS

def generate_empty_dataset():
    """Generates the full dataset structure."""
    rows = []
    for model in MODELS:
        for region in REGIONS:
            langs = get_languages_for_region(region)
            for lang in langs:
                rows.append({
                    "Model": model,
                    "Region": region,
                    "Language": lang,
                    "Language": lang,
                    "Physical Stock (Input)": 0,
                    "Prev Q Demand": 0, # Read-Only (Lookback)
                    "Effective Opening Stock": 0, # Calculated
                    "Backlog Tech Refresh": 0,
                    "Break Fix": 0,
                    "Tech Refresh Eligibility": 0,
                    "New Hires": 0,
                    "Buffer": 0
                })
    return pd.DataFrame(rows)

def load_db():
    db_path = get_db_path()
    if os.path.exists(db_path):
        with open(db_path, "r") as f:
            try:
                data = json.load(f)
                return data
            except json.JSONDecodeError:
                return {}
    return {}

def save_db(db_data):
    db_path = get_db_path()
    with open(db_path, "w") as f:
        json.dump(db_data, f, indent=4)

def load_quarter_data(quarter):
    db = load_db()
    
    full_skeleton = generate_empty_dataset()
    tr_rate_found = 0.55 # Default
    pricing_config_found = {} # V2.9 Default
    
    if quarter in db:
        content = db[quarter]
        # V2.7: Support Dict (New) vs List (Legacy)
        if isinstance(content, dict) and "data" in content:
            raw_data = content["data"]
            tr_rate_found = content.get("tr_rate", 0.55)
            # V2.9: Load Pricing Config
            pricing_config_found = content.get("pricing_config", {})
        else:
            # Legacy Format: Content IS the list
            raw_data = content
            tr_rate_found = 0.55

        saved_df = pd.DataFrame(raw_data)
        if not saved_df.empty:
            # V2.8: Data Migration (Surface 7 -> SL7)
            if "Model" in saved_df.columns:
                saved_df["Model"] = saved_df["Model"].replace("Microsoft Surface 7 Laptop", "Microsoft SL7")
            
            # V3.2: Data Migration (Current Stock -> Physical Stock)
            if "Current Stock" in saved_df.columns:
                saved_df.rename(columns={"Current Stock": "Physical Stock (Input)"}, inplace=True)

            keys = ["Model", "Region", "Language"]
            full_skeleton.set_index(keys, inplace=True)
            saved_df.set_index(keys, inplace=True)
            full_skeleton.update(saved_df)
            df = full_skeleton.reset_index()
            
            numeric_cols = ["Physical Stock (Input)", "Backlog Tech Refresh", "Break Fix", 
                            "Tech Refresh Eligibility", "New Hires", "Buffer"]
            for col in numeric_cols:
                # Ensure col exists (robustness for old data)
                if col not in df.columns:
                    df[col] = 0.0
                df[col] = df[col].astype(float)
        else:
            df = full_skeleton
    else:
        df = full_skeleton
    

    
    # --- V3.2: LOOKBACK LOGIC ---
    # 1. Identify Previous Quarter
    prev_q_name = get_previous_quarter_name(quarter)
    
    # 2. Load Prev Q Data (if exists)
    prev_demand_map = {} # (Region, Model, Language) -> Total Demand
    
    if prev_q_name and prev_q_name in db:
        content = db[prev_q_name]
        # Handle dict vs list format
        if isinstance(content, dict) and "data" in content:
            raw_prev = content["data"]
            prev_tr_rate = content.get("tr_rate", 0.55)
        else:
            raw_prev = content
            prev_tr_rate = 0.55
            
        df_prev = pd.DataFrame(raw_prev)
        if not df_prev.empty and "Model" in df_prev.columns:
             # Handle Data Migration (Surface 7 -> SL7) for prev data too, to ensure match
            df_prev["Model"] = df_prev["Model"].replace("Microsoft Surface 7 Laptop", "Microsoft SL7")
            
            # Ensure columns exist (handle older data versions)
            for col in ["Backlog Tech Refresh", "Break Fix", "Tech Refresh Eligibility", "New Hires"]:
                if col not in df_prev.columns: df_prev[col] = 0.0
                
            # Calculate Total Demand for Prev Q
            # Demand = Backlog + BreakFix + (Eligible * Rate) + NewHires
            # Calculate Total Demand for Prev Q
            # Demand = Backlog + BreakFix + (Eligible * Rate) + NewHires
            # V3.5: Round UP to nearest Integer
            raw_demand = (
                df_prev["Backlog Tech Refresh"].astype(float) +
                df_prev["Break Fix"].astype(float) +
                (df_prev["Tech Refresh Eligibility"].astype(float) * prev_tr_rate) +
                df_prev["New Hires"].astype(float)
            )
            df_prev["Calculated_Demand"] = raw_demand.apply(lambda x: int(math.ceil(x)))
            
            # Create Map
            for _, row in df_prev.iterrows():
                key = (row.get("Region"), row.get("Model"), row.get("Language"))
                prev_demand_map[key] = row["Calculated_Demand"]

    # 3. Apply to Current DF
    # If "Current Stock" exists from old data, rename it to "Physical Stock (Input)"
    if "Current Stock" in df.columns:
        df.rename(columns={"Current Stock": "Physical Stock (Input)"}, inplace=True)
        
    # Ensure new columns exist
    if "Physical Stock (Input)" not in df.columns:
        df["Physical Stock (Input)"] = 0.0
        
    # Map Prev Demand & Calculate Effective Opening
    def get_prev_demand(row):
        return prev_demand_map.get((row["Region"], row["Model"], row["Language"]), 0.0)

    df["Prev Q Demand"] = df.apply(get_prev_demand, axis=1)
    df["Effective Opening Stock"] = df["Physical Stock (Input)"] - df["Prev Q Demand"]

    # Global Sorting: Region (A-Z) -> Model
    df.sort_values(by=["Region", "Model"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    return df, tr_rate_found, pricing_config_found

def save_quarter_data(quarter, df, tr_rate, pricing_config):
    db = load_db()
    # V2.9: Save Structure including pricing_config
    db[quarter] = {
        "data": df.to_dict(orient="records"),
        "tr_rate": tr_rate,
        "pricing_config": pricing_config
    }
    save_db(db)

def create_pdf(df, quarter):
    # Ensure PDF is sorted
    df = df.sort_values(by=["Region", "Model"])
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, f'Procurement Request - {quarter}', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    cols = ["Model", "Region", "Language", "Qty", "Unit Price", "Line Total"]
    line_height = pdf.font_size * 2.5
    col_width = pdf.w / 7 

    pdf.set_font("Arial", 'B', 10)
    for col in cols:
        pdf.cell(col_width, line_height, col, border=1)
    pdf.ln(line_height)
    
    pdf.set_font("Arial", size=9)
    total_val = 0
    
    # Generic iteration handles filters automatically if df is passed appropriately
    for _, row in df.iterrows():
        pdf.cell(col_width, line_height, str(row["Model"]), border=1)
        pdf.cell(col_width, line_height, str(row["Region"]), border=1)
        pdf.cell(col_width, line_height, str(row["Language"]), border=1)
        pdf.cell(col_width, line_height, str(int(row["Quantity"])), border=1)
        pdf.cell(col_width, line_height, f"${row['Unit Price']:,.0f}", border=1)
        pdf.cell(col_width, line_height, f"${row['Total Line Cost']:,.0f}", border=1)
        pdf.ln(line_height)
        total_val += row['Total Line Cost']
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Grand Total: ${total_val:,.2f}", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

def main():
    # V2.2: Compact Header CSS
    st.markdown("""
        <style>
        /* Compact Header - Reduce top padding */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 5rem;
        }
        /* Custom Table Colors for Dark Mode (if active) */
        div[data-testid="stDataEditor"] {
            color-scheme: dark;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ App Settings")
        
        # V2.2: Dynamic DB Path Editor (Top Level or Expander)
        # Using simple expander to keep sidebar tidy, but functionality is seamless
        with st.expander("📂 Database Location", expanded=True):
            current_config = load_config()
            db_val = current_config.get("database_path", "forecast_db.json")
            
            # Cross-Platform: Normalize path separators to current OS
            db_val = os.path.normpath(db_val)
            
            new_db_path = st.text_input("Database Path", value=db_val, help="Enter path to forecast_db.json (Local or Network)")
            
            if new_db_path != db_val:
                current_config["database_path"] = new_db_path
                save_config(current_config)
                st.success("Path saved! Reloading...")
                st.rerun()
                
            st.caption(f"Reading from: `{os.path.abspath(get_db_path())}`")

        # V3.1: Bulk Stock Upload
        with st.expander("📂 Upload Stock Report (CSV)"):
            uploaded_file = st.file_uploader("Upload CSV", type=["csv"], help="Upload a stock report CSV to update Current Stock for the active quarter.")
            if uploaded_file is not None:
                if st.button("Process File"):
                    count, error = process_stock_upload(uploaded_file)
                    if error:
                        st.error(f"Failed: {error}")
                    else:
                        st.success(f"Success! Updated {count} rows.")
                        # V3.2: Re-run will trigger load_quarter_data which refreshes the calc
                        st.rerun()

        # Dark Mode Toggle
        dark_mode = st.toggle("Dark Mode", value=False)
        if dark_mode:
            st.markdown("""
            <style>
            .stApp {
                background-color: #0E1117;
                color: #FAFAFA;
            }
            [data-testid="stSidebar"] {
                background-color: #262730;
                color: #FAFAFA;
            }
            div[data-testid="stNumberInput"] input {
                color: white;
                background-color: #31333F;
            }
            p, h1, h2, h3, label, div[data-testid="stMetricValue"] {
                color: #FAFAFA !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
        st.divider()
        st.header("🗓️ Period")
        selected_quarter = st.selectbox(
            "Quarter", 
            ["FY26 Q3", "FY26 Q4", "FY27 Q1", "FY27 Q2", "FY27 Q3", "FY27 Q4", "FY28 Q1", "FY28 Q2"],
            key="quarter_selector"
        )
        
        # Helper for Default Prices (v2.9.1 Fix: Moved up for sync usage)
        def get_default_price(region, model):
            default_price = 2000
            if region == "EMEA":
                if "MacBook 14" in model: default_price = 2075
                elif "MacBook 16" in model: default_price = 3220
                elif "SL7" in model:        default_price = 1305
            return default_price

        # Load Data Logic
        if 'loaded_quarter' not in st.session_state or st.session_state.loaded_quarter != selected_quarter:
            # v2.9: Load DF, Rate, and Pricing Config
            data, rate, pricing_cfg = load_quarter_data(selected_quarter)
            st.session_state.data_df = data
            st.session_state.tr_rate_current = rate # Sync to session
            st.session_state.loaded_quarter = selected_quarter
            
            # V2.9.1: Apply Variable Pricing Context (Explicit Sync)
            for region in REGIONS:
                for model in MODELS:
                    json_key = f"{region}_{model}"
                    
                    if json_key in pricing_cfg:
                        # Case A: Saved Price Exists -> Valid
                        st.session_state[f"price_{region}_{model}"] = pricing_cfg[json_key]
                    else:
                        # Case B: No Saved Price -> FORCE DEFAULT
                        # If we used 'del', widget might hold old value if it was dirty? 
                        # Explicitly writing default value ensures sync.
                        st.session_state[f"price_{region}_{model}"] = get_default_price(region, model)
        
        # Ensure session state has current rate initialized if first run
        if 'tr_rate_current' not in st.session_state:
             st.session_state.tr_rate_current = 0.55
        
        st.divider()
        st.header("💰 Regional Pricing")
        prices = {}
        sorted_regions = sorted(REGIONS)
        for region in sorted_regions: 
            with st.expander(f"{region}"):
                for model in MODELS:
                    key = f"price_{region}_{model}"
                    
                    # Get Default for widget initial value (if key missing)
                    default_price = get_default_price(region, model)

                    val = st.number_input(f"{model}", min_value=0, value=default_price, step=100, key=key)
                    prices[(region, model)] = val

        st.header("Filters")
        selected_models_filter = st.multiselect("Models", MODELS, default=MODELS)
        selected_regions_filter = st.multiselect("Regions", REGIONS, default=REGIONS)
        
        st.header("Parameters")
        tech_refresh_rate = st.slider(
            "Tech Refresh Adoption Rate", 0, 100, int(st.session_state.tr_rate_current * 100), 5, format="%d%%",
            key="tr_rate_slider" 
        ) / 100.0

    # --- MAIN COMPACT HEADER (V2.2) ---
    col_h1, col_h2 = st.columns([3, 1])
    col_h1.markdown("### 💻 Laptop Forecast App")
    # Display Quarter and Version in a clean box or line
    col_h2.success(f"**v3.5** | {selected_quarter} | {platform.system()}")

    # --- CALCULATION ENGINE ---
    df_calc = st.session_state.data_df.copy()
    
    # Re-Calculate Effective Opening Stock (in case User changed Physical Stock)
    df_calc["Effective Opening Stock"] = df_calc["Physical Stock (Input)"] - df_calc["Prev Q Demand"]
    
    # Verify sort
    df_calc.sort_values(by=["Region", "Model"], inplace=True)
    
    df_calc["Effective Tech Refresh"] = df_calc["Tech Refresh Eligibility"] * tech_refresh_rate
    df_calc["Total Demand"] = (
        df_calc["Backlog Tech Refresh"] + 
        df_calc["Break Fix"] + 
        df_calc["Effective Tech Refresh"] + 
        df_calc["New Hires"]
    )
    # V3.2: Target Stock Formula Update
    # Old: Target Stock = Demand + Buffer. Need = Target - Current.
    # New: Need = (Demand + Buffer) - Effective Opening.
    # To keep logic similar: Target Stock Level (Ideal) = Demand + Buffer.
    # Gap = Target - Effective Opening.
    
    df_calc["Target Stock Level"] = df_calc["Total Demand"] + df_calc["Buffer"]
    
    def calculate_needs(row):
        # V3.2: Use Effective Opening Stock
        start_stock = row["Effective Opening Stock"]
        # Double negative check: If start_stock is negative (backlog), it increases need.
        # e.g. Target 100. Start -10. Need = 100 - (-10) = 110. Correct.
        needed = row["Target Stock Level"] - start_stock
        if needed <= 0: return 0
        return math.ceil(needed)
    
    df_calc["Purchase Needs"] = df_calc.apply(calculate_needs, axis=1)
    
    def calculate_cost(row):
        price = prices.get((row["Region"], row["Model"]), 0)
        return row["Purchase Needs"] * price
        
    df_calc["Total Cost"] = df_calc.apply(calculate_cost, axis=1)

    # Apply Filters
    filtered_db = df_calc[
        (df_calc["Model"].isin(selected_models_filter)) &
        (df_calc["Region"].isin(selected_regions_filter))
    ]

    # --- EXECUTIVE DASHBOARD ---
    total_new_hires = filtered_db["New Hires"].sum()
    total_order_value = filtered_db["Total Cost"].sum()
    total_units = filtered_db["Purchase Needs"].sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("New Hires", f"{int(total_new_hires)}")
    m2.metric("Order Value", f"${total_order_value:,.2f}") 
    m3.metric("Purchase Units", f"{int(total_units)}")
    
    st.divider()

    # --- INPUT SECTION ---
    # input_cols = ["Region", "Model", "Language", "Current Stock", "Backlog Tech Refresh", "Break Fix", "Tech Refresh Eligibility", "New Hires", "Buffer"]
    
    # st.subheader("Data Input") # Removed for compactness or made smaller
    
    with st.form("input_form"):
        st.markdown(f"**Data Input ({selected_quarter})**")
        edited_input_df = st.data_editor(
            filtered_db[["Region", "Model", "Language", "Physical Stock (Input)", "Prev Q Demand", "Effective Opening Stock", "Backlog Tech Refresh", "Break Fix", "Tech Refresh Eligibility", "New Hires", "Buffer"]],
            width='stretch',
            num_rows="fixed",
            height=400, # V2.2 Fixed height for better look
            column_config={
                "Model": st.column_config.TextColumn(disabled=True),
                "Region": st.column_config.TextColumn(disabled=True),
                "Language": st.column_config.TextColumn(disabled=True),
                "Physical Stock (Input)": st.column_config.NumberColumn(required=True, label="Physical Stock (Input)"),
                "Prev Q Demand": st.column_config.NumberColumn(disabled=True, help="Total Demand from Previous Quarter (Read-Only)"),
                "Effective Opening Stock": st.column_config.NumberColumn(disabled=True, help="Physical Stock - Prev Q Demand"),
                "Backlog Tech Refresh": st.column_config.NumberColumn(min_value=0, required=True),
                "Break Fix": st.column_config.NumberColumn(min_value=0, required=True),
                "Tech Refresh Eligibility": st.column_config.NumberColumn(min_value=0, required=True),
                "New Hires": st.column_config.NumberColumn(min_value=0, required=True),
                "Buffer": st.column_config.NumberColumn(min_value=0, required=True),
            },
            key="data_editor"
        )
        
        # V3.5: Totals Row
        st.markdown("**Totals (Reference)**")
        # Columns: Current Stock (Physical), Prev Q Demand, Effective Opening, New Hires, Total Demand, Required (Needs), Cost
        # Note: filtered_db has the calculated values (Total Demand, Needs, Cost).
        # We sum from filtered_db to properly reflect the calculations.
        totals_data = {
            "Physical Stock": [int(filtered_db["Physical Stock (Input)"].sum())],
            "Prev Q Demand": [int(filtered_db["Prev Q Demand"].sum())],
            "Effect. Opening": [int(filtered_db["Effective Opening Stock"].sum())],
            "New Hires": [int(filtered_db["New Hires"].sum())],
            "Total Demand": [int(filtered_db["Total Demand"].sum())], # Demand might be float, convert for display? User asked for Integer Precision in Lookback. Demand in current Q might still be float? Filtered_db has it as float. Let's show 1 decimal or int? Prompt says "Integer Precision & Totals". Let's assume standard formatting.
            "Purch Needs": [int(filtered_db["Purchase Needs"].sum())],
            "Total Cost": [f"${filtered_db['Total Cost'].sum():,.0f}"]
        }
        st.dataframe(pd.DataFrame(totals_data), hide_index=True)

        if st.form_submit_button("💾 Save Changes"):
            st.session_state.data_df.update(edited_input_df)
            
            # V2.9: Capture Pricing Config from Session State
            current_pricing = {}
            for region in REGIONS:
                for model in MODELS:
                    s_key = f"price_{region}_{model}"
                    if s_key in st.session_state:
                        # JSON Key = "{Region}_{Model}"
                        current_pricing[f"{region}_{model}"] = st.session_state[s_key]

            # V2.9: Save All
            save_quarter_data(selected_quarter, st.session_state.data_df, tech_refresh_rate, current_pricing)
            
            # Update Session State to match save
            st.session_state.tr_rate_current = tech_refresh_rate
            st.success("Saved!")
            st.rerun()

    # --- RESULTS & PO ---
    st.divider()
    t1, t2 = st.tabs(["🔍 Detailed Results", "📑 Purchase Orders"])
    
    with t1:
        st.dataframe(
            filtered_db[["Region", "Model", "Language", "Total Demand", "Target Stock Level", "Purchase Needs", "Total Cost"]].style.format({
                "Total Demand": "{:.1f}", 
                "Target Stock Level": "{:.1f}", 
                "Purchase Needs": "{:.0f}", 
                "Total Cost": "${:,.0f}"
            }),
            width='stretch'
        )

    with t2:
        po_df = filtered_db[filtered_db["Purchase Needs"] > 0].copy()
        
        if po_df.empty:
            st.info("No purchases required.")
        else:
            po_view = po_df[["Model", "Region", "Language", "Purchase Needs", "Total Cost"]].rename(
                columns={"Purchase Needs": "Quantity", "Total Cost": "Total Line Cost"}
            ).reset_index(drop=True)
            
            po_view["Unit Price"] = po_view.apply(lambda r: prices.get((r["Region"], r["Model"]), 0), axis=1)
            po_view["Quantity"] = po_view["Quantity"].astype(int)
            po_view = po_view[["Model", "Region", "Language", "Quantity", "Unit Price", "Total Line Cost"]]
            
            st.dataframe(po_view, width='stretch')
            
            col_d1, col_d2 = st.columns(2)
            csv = po_view.to_csv(index=False).encode('utf-8')
            col_d1.download_button("📥 CSV", csv, f"PO_{selected_quarter}.csv", "text/csv")
            
            pdf_bytes = create_pdf(po_view, selected_quarter)
            col_d2.download_button("📄 PDF", data=pdf_bytes, file_name=f"PO_{selected_quarter}.pdf", mime='application/pdf')

    # --- RELEASE NOTES ---
    st.divider()
    with st.expander("📜 Version History"):
        st.markdown("""
        **v3.5 (Integer Precision & Totals)**
        - **Lookback**: `Prev Q Demand` is now rounded UP to the nearest integer.
        - **UI**: Added a "Totals" reference row below the data input table.

        **v3.4 (Extended Calendar)**
        - **Timeline**: Added `FY26 Q3` to support earlier historical data entry and smoother Lookback transitions.

        **v3.3 (Refined Region Mapping)**
        - **Upload Logic**: Added specific location mapping for UK (MLN8) and LATAM (LSP3).
        
        **v3.2 (Rolling Forecast)**
        - **Lookback Logic**: Auto-calculates Effective Opening Stock based on Prev Quarter.
        - **Calculations**: `Effective Opening = Physical Stock - Prev Q Demand`.
        - **Input**: Renamed `Current Stock` to `Physical Stock (Input)`.

        **v3.1 (Bulk Upload & Cross-Platform)**
        - **Feature**: Bulk Stock Upload via CSV (Sidebar).
        - **Core**: Fully compatible with Windows and macOS.
        - **Pathing**: Normalized file paths for Unix systems.
        - **Builds**: Native installers for both platforms.

        **v2.9.1 (Crital Fix)**
        - **Fix**: Pricing sidebar fields now strictly sync with Active Quarter context.

        **v2.9 (Period-Based Pricing)**
        - **Persistence**: Regional Pricing is now saved Per-Quarter.
        - **Context Switch**: Changing quarters updates the pricing table to that quarter's settings.

        **v2.8 (Refactoring)**
        - **Model Rename**: Renamed `Microsoft Surface 7 Laptop` to `Microsoft SL7`.
        - **Migration**: Auto-migrates legacy data to new model name.

        **v2.7 (Variable Logic)**
        - **Persistence**: `Tech Refresh Adoption Rate` is now saved per-quarter.
        - **UI**: Updated Slider Label.

        **v2.6**
        - **Data**: Added `FY26 Q4` for historical tracking.

        **v2.5 (Maintenance)**
        - **Fix**: Replaced deprecated `use_container_width` with `width` parameter.
        - **Logic**: LATAM region restricted to English.
        - **Pricing**: Updated EMEA default pricing.

        **v2.4**
        - **FY27 Fiscal Calendar Update**: Planning horizon aligned to FY27 cycle.

        - **Polish**: Updated Labels and Layout.
        - **Credits**: Added Author Information.
        
        **v2.2**
        - **UI**: Compact Header to maximize screen space.
        - **Config**: Dynamic Database Path editor in Sidebar.
        - **UX**: Split Results and POs into Tabs.
        
        **v2.1 (Portable)**
        - One-Click Launcher (`setup_and_run.bat`).
        
        **v2.0**
        - External `settings.json` for Shared Database access.
        
        **v1.0 - v1.7 legacy**
        - Core forecasting logic, Region constraints, PO Export.
        """)
        
    # --- CREDITS ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align: center; font-style: italic; color: grey;'>"
        "Created by Fabio Pierotti (Fpierotti@linkedin.com)"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
