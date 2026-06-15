import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Staff Break Monitor", page_icon="⏱️", layout="wide")

TIMEZONE = pytz.timezone("America/Vancouver")

def now_local():
    return datetime.now(TIMEZONE)

def today_local():
    return now_local().strftime("%Y-%m-%d")

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
    .shift-header { font-size: 1.1rem; font-weight: 700; color: #1E3A5F; margin: 10px 0 8px 0; }
    .metric-card {
        background: white; border-radius: 12px; padding: 20px 24px;
        box-shadow: 0 1px 4px rgba(0,0,0,.08); text-align: center; margin-bottom: 8px;
    }
    .metric-number { font-size: 2rem; font-weight: 700; color: #1E3A5F; }
    .metric-label  { font-size: 0.82rem; color: #6B7280; font-weight: 500; margin-top: 4px; }
    .badge-on-break  { background: #FEF3C7; color: #92400E; padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
    .badge-working   { background: #D1FAE5; color: #065F46; padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
    .badge-off-shift { background: #F3F4F6; color: #9CA3AF; padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
    .position-badge  { background: #EFF6FF; color: #1D4ED8; padding: 2px 8px; border-radius: 20px; font-size: 0.72rem; font-weight: 500; }
    .stButton > button { border-radius: 8px !important; font-weight: 600 !important; font-size: 0.85rem !important; padding: 0.45rem 1rem !important; width: 100% !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; overflow-x: auto; }
    .stTabs [data-baseweb="tab"] { white-space: nowrap; font-weight: 600 !important; }
    @media (max-width: 768px) {
        .page-header { padding: 16px 16px; }
        .page-header h1 { font-size: 1.2rem; }
        .metric-card { padding: 12px 8px; }
        .metric-number { font-size: 1.4rem; }
        .metric-label  { font-size: 0.65rem; }
        .block-container { padding: 1rem 0.5rem !important; }
    }
    @media (min-width: 769px) {
        .block-container { padding: 2rem 3rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
SPREADSHEET_ID = "108ue_S_as7pX8CD-dUXUPaAw5WrskilsCZXwb7kbOzY"
POSITIONS = ["Manager","Supervisor","Baker","Front Crew","Drive Thru Crew","Soup & Sandwich","Front / Drive Thru Crew"]
TOP_POSITIONS = ["Manager", "Supervisor"]

# ── Google Sheets ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_spreadsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
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

# ── Staff ─────────────────────────────────────────────────────────────────────
def load_staff():
    try:
        sheet = get_sheet("Staff List")
        data  = sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            if "Name"     not in df.columns: df["Name"]     = ""
            if "Position" not in df.columns: df["Position"] = ""
            if "Shift"    not in df.columns: df["Shift"]    = "Morning"
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip()
            def sort_key(p):
                return (0, TOP_POSITIONS.index(p)) if p in TOP_POSITIONS else (1, 99)
            df["_sort"] = df["Position"].apply(sort_key)
            df = df.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)
            return df
        else:
            sheet.clear()
            sheet.append_row(["Name","Position","Shift"])
            return pd.DataFrame(columns=["Name","Position","Shift"])
    except Exception as e:
        st.error(f"Error loading staff: {e}")
        return pd.DataFrame(columns=["Name","Position","Shift"])

def save_staff_member(name, position, shift):
    sheet = get_sheet("Staff List")
    existing = sheet.get_all_values()
    if not existing:
        sheet.append_row(["Name","Position","Shift"])
    sheet.append_row([name, position, shift])

def update_staff_row(name, new_position, new_shift):
    sheet = get_sheet("Staff List")
    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if str(row.get("Name","")).strip() == name:
            sheet.update_cell(i+2, 2, new_position)
            sheet.update_cell(i+2, 3, new_shift)
            break

def delete_staff_member(name):
    sheet = get_sheet("Staff List")
    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if str(row.get("Name","")).strip() == name:
            sheet.delete_rows(i+2)
            break

# ── Daily Status (On/Off Shift + Active Breaks) — saved to Google Sheets ──────
def load_daily_status():
    """Load today's On/Off Shift status and active breaks from Google Sheets."""
    try:
        sheet   = get_sheet("Daily Status")
        records = sheet.get_all_records()
        if not records:
            sheet.clear()
            sheet.append_row(["Date","Staff","Shift_Status","Break_In_Time"])
            return {}, {}

        today    = today_local()
        off_shift      = set()
        active_breaks  = {}

        for row in records:
            if str(row.get("Date","")).strip() == today:
                name   = str(row.get("Staff","")).strip()
                status = str(row.get("Shift_Status","")).strip()
                brk_in = str(row.get("Break_In_Time","")).strip()

                if status == "Off Shift":
                    off_shift.add(name)
                if brk_in and brk_in != "":
                    try:
                        # Parse the saved break-in time
                        naive_dt = datetime.strptime(f"{today} {brk_in}", "%Y-%m-%d %H:%M:%S")
                        aware_dt = TIMEZONE.localize(naive_dt)
                        active_breaks[name] = aware_dt
                    except:
                        pass

        return off_shift, active_breaks
    except Exception as e:
        st.error(f"Error loading daily status: {e}")
        return set(), {}

def save_shift_status(staff, shift_key, status):
    """Save On/Off Shift status for a staff member today."""
    try:
        sheet   = get_sheet("Daily Status")
        records = sheet.get_all_records()
        today   = today_local()

        # Find existing row for today + staff
        for i, row in enumerate(records):
            if str(row.get("Date","")).strip() == today and str(row.get("Staff","")).strip() == staff:
                sheet.update_cell(i+2, 3, status)
                return

        # No existing row — create new one
        sheet.append_row([today, staff, status, ""])
    except Exception as e:
        st.error(f"Error saving shift status: {e}")

def save_break_in(staff, shift_key, break_in_time):
    """Save break-in time for a staff member today."""
    try:
        sheet   = get_sheet("Daily Status")
        records = sheet.get_all_records()
        today   = today_local()

        for i, row in enumerate(records):
            if str(row.get("Date","")).strip() == today and str(row.get("Staff","")).strip() == staff:
                sheet.update_cell(i+2, 4, break_in_time.strftime("%H:%M:%S"))
                return

        sheet.append_row([today, staff, "On Shift", break_in_time.strftime("%H:%M:%S")])
    except Exception as e:
        st.error(f"Error saving break in: {e}")

def clear_break_in(staff):
    """Clear break-in time after break out."""
    try:
        sheet   = get_sheet("Daily Status")
        records = sheet.get_all_records()
        today   = today_local()

        for i, row in enumerate(records):
            if str(row.get("Date","")).strip() == today and str(row.get("Staff","")).strip() == staff:
                sheet.update_cell(i+2, 4, "")
                return
    except Exception as e:
        st.error(f"Error clearing break in: {e}")

# ── Break Logs ────────────────────────────────────────────────────────────────
def load_logs():
    try:
        sheet = get_sheet("Break Logs")
        data  = sheet.get_all_records()
        if data:
            return pd.DataFrame(data)
        else:
            sheet.clear()
            sheet.append_row(["Staff","Position","Shift","Date","Break In","Break Out","Duration (min)"])
            return pd.DataFrame(columns=["Staff","Position","Shift","Date","Break In","Break Out","Duration (min)"])
    except Exception as e:
        st.error(f"Error loading logs: {e}")
        return pd.DataFrame(columns=["Staff","Position","Shift","Date","Break In","Break Out","Duration (min)"])

def save_log(staff, position, shift, date_str, break_in, break_out, duration):
    sheet = get_sheet("Break Logs")
    sheet.append_row([staff, position, shift, date_str, break_in, break_out, duration])

# ── Session state — load from Google Sheets on first load ─────────────────────
if "initialized" not in st.session_state:
    st.session_state.staff_df      = load_staff()
    off_shift, active_breaks       = load_daily_status()
    st.session_state.off_shift     = off_shift
    # Convert active_breaks keys to full shift key format
    staff_df_init = st.session_state.staff_df
    full_breaks = {}
    for staff_name, break_time in active_breaks.items():
        # Find which shift this staff belongs to
        if not staff_df_init.empty and "Shift" in staff_df_init.columns:
            match = staff_df_init[staff_df_init["Name"] == staff_name]
            if not match.empty:
                shift_name = match.iloc[0]["Shift"]
                full_breaks[f"{shift_name}_{staff_name}"] = break_time
    st.session_state.active_breaks = full_breaks
    st.session_state.initialized   = True

staff_df = st.session_state.staff_df
logs_df  = load_logs()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-header"><h1>⏱️ Staff Break Monitor</h1><p>Track break-in and break-out times for your team in real time.</p></div>', unsafe_allow_html=True)

# ── Metrics ───────────────────────────────────────────────────────────────────
def get_shift_metrics(shift_name):
    if staff_df.empty or "Shift" not in staff_df.columns:
        return 0, 0, 0, 0
    shift_staff = staff_df[
        (staff_df["Shift"].astype(str).str.strip().str.lower() == shift_name.lower()) &
        (~staff_df["Name"].isin(st.session_state.off_shift))
    ]
    total   = len(shift_staff)
    on_brk  = sum(1 for k in st.session_state.active_breaks if k.startswith(f"{shift_name}_"))
    working = total - on_brk
    today_records = logs_df[
        (logs_df["Date"] == today_local()) & (logs_df["Shift"] == shift_name)
    ] if not logs_df.empty and "Date" in logs_df.columns else pd.DataFrame()
    avg = round(pd.to_numeric(today_records["Duration (min)"], errors="coerce").mean(), 1) if not today_records.empty else 0
    return total, working, on_brk, avg

m_total, m_working, m_break, m_avg = get_shift_metrics("Morning")
a_total, a_working, a_break, a_avg = get_shift_metrics("Afternoon")

st.markdown('<div class="shift-header">☀️ Morning Shift</div>', unsafe_allow_html=True)
mc1, mc2, mc3, mc4 = st.columns(4)
mc1.markdown(f'<div class="metric-card"><div class="metric-number">{m_total}</div><div class="metric-label">On Shift Today</div></div>', unsafe_allow_html=True)
mc2.markdown(f'<div class="metric-card"><div class="metric-number">{m_working}</div><div class="metric-label">Currently Working</div></div>', unsafe_allow_html=True)
mc3.markdown(f'<div class="metric-card"><div class="metric-number">{m_break}</div><div class="metric-label">On Break</div></div>', unsafe_allow_html=True)
mc4.markdown(f'<div class="metric-card"><div class="metric-number">{m_avg}m</div><div class="metric-label">Avg Break (today)</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<div class="shift-header">🌤️ Afternoon Shift</div>', unsafe_allow_html=True)
ac1, ac2, ac3, ac4 = st.columns(4)
ac1.markdown(f'<div class="metric-card"><div class="metric-number">{a_total}</div><div class="metric-label">On Shift Today</div></div>', unsafe_allow_html=True)
ac2.markdown(f'<div class="metric-card"><div class="metric-number">{a_working}</div><div class="metric-label">Currently Working</div></div>', unsafe_allow_html=True)
ac3.markdown(f'<div class="metric-card"><div class="metric-number">{a_break}</div><div class="metric-label">On Break</div></div>', unsafe_allow_html=True)
ac4.markdown(f'<div class="metric-card"><div class="metric-number">{a_avg}m</div><div class="metric-label">Avg Break (today)</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_morning, tab_afternoon, tab_logs, tab_manage = st.tabs([
    "☀️ Morning Shift", "🌤️ Afternoon Shift", "📋 Break Log", "👥 Manage Staff"
])

def render_shift(shift_name):
    if st.button(f"🔄 Refresh", key=f"refresh_{shift_name}"):
        st.session_state.staff_df = load_staff()
        st.rerun()

    current_staff = st.session_state.staff_df
    if current_staff.empty:
        st.info("No staff added yet. Go to **Manage Staff** tab to add members.")
        return
    if "Shift" not in current_staff.columns:
        st.warning("Shift column missing. Please re-save staff in Manage Staff tab.")
        return

    shift_staff = current_staff[
        current_staff["Shift"].astype(str).str.strip().str.lower() == shift_name.lower()
    ].copy()

    if shift_staff.empty:
        st.info(f"No staff assigned to {shift_name} Shift.")
        return

    for _, row in shift_staff.iterrows():
        staff     = str(row.get("Name","")).strip()
        position  = str(row.get("Position","")).strip()
        key_id    = f"{shift_name}_{staff}"
        is_off    = staff in st.session_state.off_shift
        on_break  = key_id in st.session_state.active_breaks

        col_info, col_toggle, col_btn = st.columns([3, 1.2, 1])

        if is_off:
            badge = '<span class="badge-off-shift">Not Working Today</span>'
        elif on_break:
            badge = '<span class="badge-on-break">On Break</span>'
        else:
            badge = '<span class="badge-working">Working</span>'

        pos_badge  = f'<span class="position-badge">{position}</span>'
        start_time = f"since {st.session_state.active_breaks[key_id].strftime('%H:%M')}" if on_break else ""

        col_info.markdown(
            f"**{staff}**<br>{badge} {pos_badge}<br>"
            f"<span style='font-size:0.75rem;color:#9CA3AF'>{start_time}</span>",
            unsafe_allow_html=True
        )

        shift_status = col_toggle.radio(
            "",
            ["On Shift", "Off Shift"],
            index=1 if is_off else 0,
            key=f"status_{key_id}",
            horizontal=False,
            label_visibility="collapsed"
        )

        if not isinstance(st.session_state.off_shift, set):
            st.session_state.off_shift = set(st.session_state.off_shift)
        if shift_status == "Off Shift" and staff not in st.session_state.off_shift:
            st.session_state.off_shift.add(staff)
            save_shift_status(staff, key_id, "Off Shift")
            if key_id in st.session_state.active_breaks:
                st.session_state.active_breaks.pop(key_id)
                clear_break_in(staff)
            st.rerun()
        elif shift_status == "On Shift" and staff in st.session_state.off_shift:
            st.session_state.off_shift.discard(staff)
            save_shift_status(staff, key_id, "On Shift")
            st.rerun()

        if not is_off:
            if on_break:
                if col_btn.button("Break Out", key=f"out_{key_id}"):
                    break_in_dt  = st.session_state.active_breaks.pop(key_id)
                    break_out_dt = now_local()
                    duration     = round((break_out_dt - break_in_dt).total_seconds()/60, 1)
                    save_log(staff, position, shift_name, today_local(),
                             break_in_dt.strftime("%H:%M:%S"),
                             break_out_dt.strftime("%H:%M:%S"), duration)
                    clear_break_in(staff)
                    st.toast(f"✅ {staff} back ({duration} min)")
                    st.rerun()
            else:
                if col_btn.button("Break In", key=f"in_{key_id}"):
                    break_time = now_local()
                    st.session_state.active_breaks[key_id] = break_time
                    save_break_in(staff, key_id, break_time)
                    st.toast(f"☕ {staff} on break")
                    st.rerun()
        else:
            col_btn.markdown("")

        st.divider()

with tab_morning:
    st.subheader("☀️ Morning Shift")
    render_shift("Morning")

with tab_afternoon:
    st.subheader("🌤️ Afternoon Shift")
    render_shift("Afternoon")

with tab_logs:
    st.subheader("📋 Break Log")
    if st.button("🔄 Refresh Logs"):
        st.rerun()
    filter_staff = st.selectbox("Filter by staff", ["All"] + (staff_df["Name"].tolist() if not staff_df.empty else []))
    filter_shift = st.selectbox("Filter by shift", ["All","Morning","Afternoon"])
    filter_date  = st.date_input("Filter by date", value=date.today())
    logs = logs_df.copy()
    if not logs.empty and "Date" in logs.columns:
        logs = logs[logs["Date"] == str(filter_date)]
        if filter_staff != "All": logs = logs[logs["Staff"] == filter_staff]
        if filter_shift != "All": logs = logs[logs["Shift"] == filter_shift]
    if logs.empty:
        st.info("No break records found.")
    else:
        def highlight_long(val):
            try: return f"background-color: {'#FEE2E2' if float(val) > 30 else ''}"
            except: return ""
        try:
            styled = logs.sort_values("Break In", ascending=False).style.map(highlight_long, subset=["Duration (min)"]).format({"Duration (min)": "{:.1f}"})
        except AttributeError:
            styled = logs.sort_values("Break In", ascending=False).style.applymap(highlight_long, subset=["Duration (min)"]).format({"Duration (min)": "{:.1f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download CSV", logs.to_csv(index=False).encode(), f"break_log_{today_local()}.csv", "text/csv")
    if not logs_df.empty and "Date" in logs_df.columns:
        today_logs = logs_df[logs_df["Date"] == today_local()]
        if not today_logs.empty:
            st.markdown("#### Today's Summary")
            summary = today_logs.groupby(["Staff","Position","Shift"]).agg(
                Breaks=("Duration (min)","count"),
                Total_Minutes=("Duration (min)","sum")
            ).reset_index().rename(columns={"Total_Minutes":"Total Break (min)"}).sort_values("Total Break (min)", ascending=False)
            st.dataframe(summary, use_container_width=True, hide_index=True)

with tab_manage:
    st.subheader("👥 Manage Staff")
    with st.expander("➕ Add New Staff Member", expanded=True):
        new_name     = st.text_input("Full Name", placeholder="e.g. John Smith")
        new_position = st.selectbox("Position", POSITIONS, key="new_position")
        new_shift    = st.radio("Shift", ["Morning","Afternoon"], horizontal=True, key="new_shift")
        if st.button("➕ Add Staff Member"):
            if new_name.strip():
                existing = staff_df["Name"].tolist() if not staff_df.empty else []
                if new_name.strip() in existing:
                    st.warning("Already exists.")
                else:
                    save_staff_member(new_name.strip(), new_position, new_shift)
                    st.session_state.staff_df = load_staff()
                    st.success(f"✅ Added {new_name.strip()} — {new_position} | {new_shift}")
                    st.rerun()
            else:
                st.warning("Please enter a name.")
    st.markdown("---")
    st.markdown("#### Current Staff")
    st.caption("⭐ Manager/Supervisor always at top. 💾 save · 🗑️ remove")
    if staff_df.empty:
        st.info("No staff yet. Add one above!")
    else:
        for _, row in staff_df.iterrows():
            staff_name  = str(row.get("Name","")).strip()
            staff_pos   = str(row.get("Position", POSITIONS[0])).strip()
            staff_shift = str(row.get("Shift", "Morning")).strip()
            is_top      = staff_pos in TOP_POSITIONS
            with st.container():
                st.markdown(f"{'⭐ ' if is_top else ''}**{staff_name}**")
                pos_index   = POSITIONS.index(staff_pos) if staff_pos in POSITIONS else 0
                new_pos     = st.selectbox("Position", POSITIONS, index=pos_index, key=f"pos_{staff_name}")
                shift_index = 0 if staff_shift.lower() == "morning" else 1
                new_shift   = st.radio("Shift", ["Morning","Afternoon"], index=shift_index, key=f"shift_{staff_name}", horizontal=True)
                col_save, col_del = st.columns(2)
                if col_save.button("💾 Save", key=f"save_{staff_name}"):
                    update_staff_row(staff_name, new_pos, new_shift)
                    st.session_state.staff_df = load_staff()
                    st.toast(f"✅ Updated {staff_name}")
                    st.rerun()
                if col_del.button("🗑️ Remove", key=f"del_{staff_name}"):
                    delete_staff_member(staff_name)
                    st.session_state.staff_df = load_staff()
                    st.toast(f"🗑️ Removed {staff_name}")
                    st.rerun()
            st.divider()
