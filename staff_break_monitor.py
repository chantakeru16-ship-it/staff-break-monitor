import streamlit as st
import pandas as pd
from datetime import datetime, date
import gspread
from google.oauth2.service_account import Credentials
import time

st.set_page_config(page_title="Staff Break Monitor", page_icon="⏱️", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #F7F8FA; }
    .page-header {
        background: linear-gradient(135deg, #1E3A5F 0%, #2E6DA4 100%);
        color: white; padding: 28px 32px; border-radius: 14px; margin-bottom: 28px;
    }
    .page-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .page-header p  { margin: 6px 0 0; opacity: 0.8; font-size: 0.9rem; }
    .metric-card {
        background: white; border-radius: 12px; padding: 20px 24px;
        box-shadow: 0 1px 4px rgba(0,0,0,.08); text-align: center;
    }
    .metric-number { font-size: 2rem; font-weight: 700; color: #1E3A5F; }
    .metric-label  { font-size: 0.82rem; color: #6B7280; font-weight: 500; margin-top: 4px; }
    .badge-on-break { background: #FEF3C7; color: #92400E; padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
    .badge-working  { background: #D1FAE5; color: #065F46; padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
    .position-badge { background: #EFF6FF; color: #1D4ED8; padding: 2px 8px; border-radius: 20px; font-size: 0.72rem; font-weight: 500; }
    .stButton > button { border-radius: 8px !important; font-weight: 600 !important; font-size: 0.85rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
SPREADSHEET_ID = "108ue_S_as7pX8CD-dUXUPaAw5WrskilsCZXwb7kbOzY"
POSITIONS = ["Manager","Supervisor","Baker","Front Crew","Drive Thru Crew","Soup & Sandwich","Front / Drive Thru Crew"]
TOP_POSITIONS = ["Manager", "Supervisor"]

# ── Google Sheets — connect ONCE, cache for 10 minutes ───────────────────────
@st.cache_resource
def get_spreadsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)

def get_sheet(name):
    spreadsheet = get_spreadsheet()
    try:
        return spreadsheet.worksheet(name)
    except:
        sheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=10)
        return sheet

# ── Cached data loads — only re-read when explicitly refreshed ────────────────
@st.cache_data(ttl=300)
def load_staff():
    try:
        sheet = get_sheet("Staff List")
        data  = sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            df["_p"] = df["Position"].apply(lambda p: (0, TOP_POSITIONS.index(p)) if p in TOP_POSITIONS else (1, 99))
            df = df.sort_values("_p").drop(columns=["_p"]).reset_index(drop=True)
            return df
        else:
            sheet.append_row(["Name","Position","Shift"])
            return pd.DataFrame(columns=["Name","Position","Shift"])
    except Exception as e:
        st.error(f"Error loading staff: {e}")
        return pd.DataFrame(columns=["Name","Position","Shift"])

@st.cache_data(ttl=300)
def load_logs():
    try:
        sheet = get_sheet("Break Logs")
        data  = sheet.get_all_records()
        if data:
            return pd.DataFrame(data)
        else:
            sheet.append_row(["Staff","Position","Shift","Date","Break In","Break Out","Duration (min)"])
            return pd.DataFrame(columns=["Staff","Position","Shift","Date","Break In","Break Out","Duration (min)"])
    except Exception as e:
        st.error(f"Error loading logs: {e}")
        return pd.DataFrame(columns=["Staff","Position","Shift","Date","Break In","Break Out","Duration (min)"])

# ── Write functions ───────────────────────────────────────────────────────────
def save_staff_member(name, position, shift):
    sheet = get_sheet("Staff List")
    records = sheet.get_all_records()
    if not records:
        sheet.append_row(["Name","Position","Shift"])
    sheet.append_row([name, position, shift])
    load_staff.clear()

def update_staff_row(name, new_position, new_shift):
    sheet   = get_sheet("Staff List")
    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if row["Name"] == name:
            sheet.update_cell(i+2, 2, new_position)
            sheet.update_cell(i+2, 3, new_shift)
            break
    load_staff.clear()

def delete_staff_member(name):
    sheet   = get_sheet("Staff List")
    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if row["Name"] == name:
            sheet.delete_rows(i+2)
            break
    load_staff.clear()

def save_log(staff, position, shift, date_str, break_in, break_out, duration):
    sheet = get_sheet("Break Logs")
    sheet.append_row([staff, position, shift, date_str, break_in, break_out, duration])
    load_logs.clear()

# ── Session state ─────────────────────────────────────────────────────────────
if "active_breaks" not in st.session_state:
    st.session_state.active_breaks = {}

def today_str(): return date.today().strftime("%Y-%m-%d")

# ── Load data ─────────────────────────────────────────────────────────────────
staff_df = load_staff()
logs_df  = load_logs()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-header"><h1>⏱️ Staff Break Monitor</h1><p>Track break-in and break-out times for your team in real time.</p></div>', unsafe_allow_html=True)

# ── Metrics ───────────────────────────────────────────────────────────────────
total_staff   = len(staff_df)
on_break      = len(st.session_state.active_breaks)
working       = total_staff - on_break
today_records = logs_df[logs_df["Date"] == today_str()] if not logs_df.empty and "Date" in logs_df.columns else pd.DataFrame()
avg_duration  = round(pd.to_numeric(today_records["Duration (min)"], errors="coerce").mean(), 1) if not today_records.empty else 0

c1, c2, c3, c4 = st.columns(4)
for col, num, label in [(c1, total_staff, "Total Staff"), (c2, working, "Currently Working"), (c3, on_break, "On Break"), (c4, f"{avg_duration}m", "Avg Break (today)")]:
    col.markdown(f'<div class="metric-card"><div class="metric-number">{num}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_morning, tab_afternoon, tab_logs, tab_manage = st.tabs([
    "☀️ Morning Shift", "🌤️ Afternoon Shift", "📋 Break Log", "👥 Manage Staff"
])

def render_shift(shift_name):
    if staff_df.empty:
        st.info("No staff added yet. Go to **Manage Staff** tab to add staff members.")
        return
    shift_staff = staff_df[staff_df["Shift"] == shift_name] if "Shift" in staff_df.columns else pd.DataFrame()
    if shift_staff.empty:
        st.info(f"No staff assigned to {shift_name} Shift. Go to **Manage Staff** to assign shifts.")
        return
    for _, row in shift_staff.iterrows():
        staff    = row["Name"]
        position = row.get("Position","")
        key_id   = f"{shift_name}_{staff}"
        on       = key_id in st.session_state.active_breaks
        badge    = '<span class="badge-on-break">On Break</span>' if on else '<span class="badge-working">Working</span>'
        pos_badge = f'<span class="position-badge">{position}</span>'
        start_time = f"started {st.session_state.active_breaks[key_id].strftime('%H:%M:%S')}" if on else ""
        col_info, col_btn = st.columns([3,1])
        col_info.markdown(f"**{staff}** {badge} {pos_badge}<br><span style='font-size:0.78rem;color:#9CA3AF'>{start_time}</span>", unsafe_allow_html=True)
        if on:
            if col_btn.button("Break Out", key=f"out_{key_id}"):
                break_in_dt  = st.session_state.active_breaks.pop(key_id)
                break_out_dt = datetime.now()
                duration     = round((break_out_dt - break_in_dt).total_seconds()/60, 1)
                save_log(staff, position, shift_name, today_str(), break_in_dt.strftime("%H:%M:%S"), break_out_dt.strftime("%H:%M:%S"), duration)
                st.toast(f"✅ {staff} returned from break ({duration} min)")
                st.rerun()
        else:
            if col_btn.button("Break In", key=f"in_{key_id}"):
                st.session_state.active_breaks[key_id] = datetime.now()
                st.toast(f"☕ {staff} started break")
                st.rerun()
        st.divider()

with tab_morning:
    st.subheader("☀️ Morning Shift Staff")
    render_shift("Morning")

with tab_afternoon:
    st.subheader("🌤️ Afternoon Shift Staff")
    render_shift("Afternoon")

# ── Break Log Tab ─────────────────────────────────────────────────────────────
with tab_logs:
    st.subheader("📋 Break Log")
    if st.button("🔄 Refresh Logs"):
        load_logs.clear()
        st.rerun()

    f1, f2, f3 = st.columns(3)
    filter_staff = f1.selectbox("Filter by staff", ["All"] + (staff_df["Name"].tolist() if not staff_df.empty else []))
    filter_shift = f2.selectbox("Filter by shift", ["All","Morning","Afternoon"])
    filter_date  = f3.date_input("Filter by date", value=date.today())

    logs = logs_df.copy()
    if not logs.empty and "Date" in logs.columns:
        logs = logs[logs["Date"] == str(filter_date)]
        if filter_staff != "All": logs = logs[logs["Staff"] == filter_staff]
        if filter_shift != "All": logs = logs[logs["Shift"] == filter_shift]

    if logs.empty:
        st.info("No break records found for the selected filters.")
    else:
        def highlight_long(val):
            try: return f"background-color: {'#FEE2E2' if float(val) > 30 else ''}"
            except: return ""
        try:
            styled = logs.sort_values("Break In", ascending=False).style.map(highlight_long, subset=["Duration (min)"]).format({"Duration (min)": "{:.1f}"})
        except AttributeError:
            styled = logs.sort_values("Break In", ascending=False).style.applymap(highlight_long, subset=["Duration (min)"]).format({"Duration (min)": "{:.1f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download as CSV", logs.to_csv(index=False).encode(), f"break_log_{today_str()}.csv", "text/csv")

    if not logs_df.empty and "Date" in logs_df.columns:
        today_logs = logs_df[logs_df["Date"] == today_str()]
        if not today_logs.empty:
            st.markdown("#### Today's Summary by Staff")
            summary = today_logs.groupby(["Staff","Position","Shift"]).agg(
                Breaks=("Duration (min)","count"),
                Total_Minutes=("Duration (min)","sum")
            ).reset_index().rename(columns={"Total_Minutes":"Total Break (min)"}).sort_values("Total Break (min)", ascending=False)
            st.dataframe(summary, use_container_width=True, hide_index=True)

# ── Manage Staff Tab ──────────────────────────────────────────────────────────
with tab_manage:
    st.subheader("👥 Manage Staff")

    with st.expander("➕ Add New Staff Member", expanded=True):
        new_name     = st.text_input("Full Name", placeholder="e.g. John Smith")
        new_position = st.selectbox("Position", POSITIONS, key="new_position")
        new_shift    = st.radio("Shift Assignment", ["Morning","Afternoon"], horizontal=True, key="new_shift")
        if st.button("➕ Add Staff Member"):
            if new_name.strip():
                existing = staff_df["Name"].tolist() if not staff_df.empty else []
                if new_name.strip() in existing:
                    st.warning("This staff member already exists.")
                else:
                    save_staff_member(new_name.strip(), new_position, new_shift)
                    st.success(f"✅ Added **{new_name.strip()}** — {new_position} | {new_shift} Shift")
                    st.rerun()
            else:
                st.warning("Please enter a name.")

    st.markdown("---")
    st.markdown("#### Current Staff Members")
    st.caption("⭐ Manager and Supervisor always appear at the top. Use 💾 to save changes, 🗑️ to remove.")

    if staff_df.empty:
        st.info("No staff members yet. Add one above!")
    else:
        h1, h2, h3, h4, h5 = st.columns([2,2,2,0.5,0.5])
        h1.markdown("**Name**"); h2.markdown("**Position**"); h3.markdown("**Shift**")

        for _, row in staff_df.iterrows():
            staff_name  = row["Name"]
            staff_pos   = row.get("Position", POSITIONS[0])
            staff_shift = row.get("Shift", "Morning")

            col_name, col_pos, col_shift, col_save, col_del = st.columns([2,2,2,0.5,0.5])

            is_top = staff_pos in TOP_POSITIONS
            col_name.markdown(f"{'⭐ ' if is_top else ''}**{staff_name}**")

            pos_index   = POSITIONS.index(staff_pos) if staff_pos in POSITIONS else 0
            new_pos     = col_pos.selectbox("", POSITIONS, index=pos_index, key=f"pos_{staff_name}", label_visibility="collapsed")
            shift_index = 0 if staff_shift == "Morning" else 1
            new_shift   = col_shift.radio("", ["Morning","Afternoon"], index=shift_index, key=f"shift_{staff_name}", horizontal=True, label_visibility="collapsed")

            if col_save.button("💾", key=f"save_{staff_name}", help="Save changes"):
                update_staff_row(staff_name, new_pos, new_shift)
                st.toast(f"✅ Updated {staff_name}")
                st.rerun()

            if col_del.button("🗑️", key=f"del_{staff_name}", help="Remove staff"):
                delete_staff_member(staff_name)
                st.toast(f"🗑️ Removed {staff_name}")
                st.rerun()

            st.divider()
