import os
import gzip
import sqlite3
import datetime
import streamlit as st

st.set_page_config(
    page_title="Prior Scan Checker",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom mobile-friendly clean CSS
st.markdown("""
<style>
    /* Clean healthcare dark / modern look */
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .header-box {
        text-align: center;
        padding: 1.5rem 0 1rem 0;
    }
    .header-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #FFFFFF;
        letter-spacing: -0.5px;
        margin-bottom: 0.2rem;
    }
    .header-sub {
        font-size: 0.95rem;
        color: #94A3B8;
    }
    /* Clean custom table */
    .scan-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
        background: #1E293B;
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #334155;
    }
    .scan-table th {
        background: #162032;
        color: #94A3B8;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 10px 16px;
        border-bottom: 1px solid #334155;
        text-align: left;
    }
    .scan-table td {
        padding: 12px 16px;
        border-bottom: 1px solid #293548;
        font-size: 0.95rem;
    }
    .scan-table tr:last-child td {
        border-bottom: none;
    }
    .td-date {
        color: #38BDF8;
        font-family: monospace;
        font-weight: 600;
        white-space: nowrap;
        width: 140px;
    }
    .td-scan {
        color: #F8FAFC;
        font-weight: 600;
    }
    /* Hide default Streamlit footer */
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

DB_NAME = "priors_compact.db"
GZ_NAME = "priors_compact.db.gz"

@st.cache_resource(show_spinner="Preparing legacy database (takes ~2 seconds on first boot)...")
def init_database():
    """Extract gzipped SQLite database if not already extracted and return connection."""
    if not os.path.exists(DB_NAME):
        if os.path.exists(GZ_NAME):
            with gzip.open(GZ_NAME, "rb") as f_in, open(DB_NAME, "wb") as f_out:
                while chunk := f_in.read(1024 * 1024 * 4):
                    f_out.write(chunk)
        else:
            raise FileNotFoundError("Neither priors_compact.db nor priors_compact.db.gz was found.")
    
    conn = sqlite3.connect(f"file:{os.path.abspath(DB_NAME)}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def format_clean_date(dt_str):
    if not dt_str:
        return "Unknown"
    s = str(dt_str).strip()
    try:
        if len(s) >= 10:
            dt = datetime.datetime.strptime(s[:10], "%Y-%m-%d")
            return dt.strftime("%d-%b-%Y")
    except Exception:
        pass
    return s[:10] if len(s) >= 10 else s

st.markdown("""
<div class="header-box">
    <div class="header-title">⚡ Prior Scan Checker</div>
    <div class="header-sub">Enter registration number to view previously done scans</div>
</div>
""", unsafe_allow_html=True)

try:
    conn = init_database()
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# Search form
with st.form("search_form", clear_on_submit=False):
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        reg_input = st.text_input(
            "Registration Number",
            placeholder="Enter Reg No (e.g. 183528)",
            label_visibility="collapsed"
        )
    with col_btn:
        submitted = st.form_submit_button("Search", use_container_width=True)

# Maintain recent searches in session
if "recents" not in st.session_state:
    st.session_state.recents = []

query_pid = reg_input.strip() if reg_input else ""

if query_pid:
    if query_pid not in st.session_state.recents:
        st.session_state.recents.insert(0, query_pid)
        st.session_state.recents = st.session_state.recents[:6]

    candidates = [query_pid, query_pid.upper()]
    if query_pid.isdigit() and query_pid.startswith("0"):
        candidates.append(query_pid.lstrip("0"))

    cur = conn.cursor()
    rows = []
    seen = set()

    for p in candidates:
        cur.execute("SELECT dt, scan FROM priors WHERE pid = ? ORDER BY dt DESC", (p,))
        fetched = cur.fetchall()
        if fetched:
            for r in fetched:
                key = (r["dt"], r["scan"])
                if key not in seen:
                    seen.add(key)
                    rows.append(r)
            break

    if rows:
        st.success(f"✅ Patient **{query_pid}** — {len(rows)} prior scan{'s' if len(rows) > 1 else ''} found")
        
        # Build clean HTML table
        table_html = """
        <table class="scan-table">
            <thead>
                <tr>
                    <th style="width: 140px;">Date Done</th>
                    <th>Scan Type Done</th>
                </tr>
            </thead>
            <tbody>
        """
        copy_lines = []
        for r in rows:
            clean_dt = format_clean_date(r["dt"])
            scan_text = r["scan"]
            copy_lines.append(f"{clean_dt}: {scan_text}")
            table_html += f"""
                <tr>
                    <td class="td-date">{clean_dt}</td>
                    <td class="td-scan">{scan_text}</td>
                </tr>
            """
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)

        # Quick copy area
        plain_summary = "\n".join(copy_lines)
        with st.expander("📋 Copy Plain List for PACS"):
            st.code(plain_summary, language="text")
    else:
        st.warning(f"❌ No prior scans found in archive for Patient Reg No: **{query_pid}**")

# Show recent search chips if any
if st.session_state.recents:
    st.markdown("<p style='font-size: 0.8rem; color: #64748B; margin-top: 1rem;'>Recent searches:</p>", unsafe_allow_html=True)
    chips_html = " ".join([f"<code style='color: #38BDF8; background: #1E293B; padding: 2px 8px; border-radius: 4px; margin-right: 6px;'>{r}</code>" for r in st.session_state.recents])
    st.markdown(chips_html, unsafe_allow_html=True)
