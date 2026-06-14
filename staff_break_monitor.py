import streamlit as st
import pandas as pd
from datetime import datetime, date

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
    .stButton > button { border-radius: 8px !important; font-weight: 600 !important; font-size: 0.85rem !important; }
</style>
""", unsafe_allow_html=True)

DEFAULT_STAFF = ["Alice Johnson", "Bob Martinez", "Carol Lee", "David Nguyen", "Emma Wilson", "Frank Chen"]

if "staff_list"    not in st.session_state: st.session_state.staff_list    = DEFAULT_STAFF.copy()
if "logs"          not in st.session_state: st.session_state.logs          = pd.DataFrame(columns=["Staff","Date","Break In","Break Out","Duration (min)"])
if "active_breaks" not in st.session_state: st.session_state.active_breaks = {}

def today_str(): return date.today().strftime("%Y-%m-%d")

st.markdown('<div class="page-header"><h1>⏱️ Staff Break Monitor</h1><p>Track break-in and break-out times for your team in real time.</p></div>', unsafe_allow_html=True)

total_staff   = len(st.session_state.staff_list)
on_break      = len(st.session_state.active_breaks)
working       = total_staff - on_break
today_records = st.session_state.logs[st.session_state.logs["Date"] == today_str()] if not st.session_state.logs.empty else pd.DataFrame()
avg_duration  = round(today_records["Duration (min)"].mean(), 1) if not today_records.empty and "Duration (min)" in today_records.columns else 0

c1, c2, c3, c4 = st.columns(4)
for col, num, label in [(c1, total_staff, "Total Staff"), (c2, working, "Currently Working"), (c3, on_break, "On Break"), (c4, f"{avg_duration}m", "Avg Break (today)")]:
    col.markdown(f'<div class="metric-card"><div class="metric-number">{num}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
left, right = st.columns([1, 1.6], gap="large")

with left:
    st.subheader("🧑‍💼 Staff Status")
    for staff in st.session_state.staff_list:
        on = staff in st.session_state.active_breaks
        badge = '<span class="badge-on-break">On Break</span>' if on else '<span class="badge-working">Working</span>'
        start_time = f"started {st.session_state.active_breaks[staff].strftime('%H:%M:%S')}" if on else ""
        row_left, row_right = st.columns([2, 1])
        row_left.markdown(f"**{staff}** {badge}<br><span style='font-size:0.78rem;color:#9CA3AF'>{start_time}</span>", unsafe_allow_html=True)
        if on:
            if row_right.button("Break Out", key=f"out_{staff}"):
                break_in_dt  = st.session_state.active_breaks.pop(staff)
                break_out_dt = datetime.now()
                duration     = round((break_out_dt - break_in_dt).total_seconds() / 60, 1)
                new_row = pd.DataFrame([{"Staff": staff, "Date": today_str(), "Break In": break_in_dt.strftime("%H:%M:%S"), "Break Out": break_out_dt.strftime("%H:%M:%S"), "Duration (min)": duration}])
                st.session_state.logs = pd.concat([st.session_state.logs, new_row], ignore_index=True)
                st.toast(f"✅ {staff} returned from break ({duration} min)")
                st.rerun()
        else:
            if row_right.button("Break In", key=f"in_{staff}"):
                st.session_state.active_breaks[staff] = datetime.now()
                st.toast(f"☕ {staff} started break")
                st.rerun()
        st.divider()

    with st.expander("➕ Manage Staff"):
        new_name = st.text_input("New staff name", placeholder="Full name")
        if st.button("Add Staff") and new_name.strip():
            if new_name.strip() not in st.session_state.staff_list:
                st.session_state.staff_list.append(new_name.strip())
                st.success(f"Added {new_name.strip()}")
                st.rerun()
            else:
                st.warning("Staff member already exists.")
        remove_name = st.selectbox("Remove staff", ["— select —"] + st.session_state.staff_list)
        if st.button("Remove Staff") and remove_name != "— select —":
            st.session_state.staff_list.remove(remove_name)
            st.session_state.active_breaks.pop(remove_name, None)
            st.success(f"Removed {remove_name}")
            st.rerun()

with right:
    st.subheader("📋 Break Log")
    filter_col1, filter_col2 = st.columns(2)
    filter_staff = filter_col1.selectbox("Filter by staff", ["All"] + st.session_state.staff_list)
    filter_date  = filter_col2.date_input("Filter by date", value=date.today())
    logs = st.session_state.logs.copy()
    if not logs.empty:
        if filter_staff != "All": logs = logs[logs["Staff"] == filter_staff]
        logs = logs[logs["Date"] == str(filter_date)]
    if logs.empty:
        st.info("No break records found for the selected filters.")
    else:
        def highlight_long(val):
            return f"background-color: {'#FEE2E2' if float(val) > 30 else ''}"
        try:
            styled = logs.sort_values("Break In", ascending=False).style.map(highlight_long, subset=["Duration (min)"]).format({"Duration (min)": "{:.1f}"})
        except AttributeError:
            styled = logs.sort_values("Break In", ascending=False).style.applymap(highlight_long, subset=["Duration (min)"]).format({"Duration (min)": "{:.1f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download as CSV", logs.to_csv(index=False).encode(), f"break_log_{today_str()}.csv", "text/csv")

    if not st.session_state.logs.empty:
        today_logs = st.session_state.logs[st.session_state.logs["Date"] == today_str()]
        if not today_logs.empty:
            st.markdown("#### Today's Summary by Staff")
            summary = today_logs.groupby("Staff").agg(Breaks=("Duration (min)","count"), Total_Minutes=("Duration (min)","sum")).reset_index().rename(columns={"Total_Minutes":"Total Break (min)"}).sort_values("Total Break (min)", ascending=False)
            st.dataframe(summary, use_container_width=True, hide_index=True)
