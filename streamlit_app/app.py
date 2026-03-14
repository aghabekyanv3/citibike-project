"""
app.py  –  Entry point for the Citi Bike JC/Hoboken Streamlit dashboard.
Run with:  streamlit run app.py
"""

import streamlit as st
from utils import apply_global_css, COLORS

st.set_page_config(
    page_title="Citi Bike · Jersey City & Hoboken",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()

# ── Sidebar branding ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div style="text-align:center; padding: 1.5rem 0 1rem 0;">
            <div style="font-size:2.5rem;">🚲</div>
            <div style="font-size:1.2rem; font-weight:700; color:#fff; letter-spacing:.02em;">
                CITI BIKE
            </div>
            <div style="font-size:.75rem; color:rgba(255,255,255,.65);
                        text-transform:uppercase; letter-spacing:.1em;">
                Jersey City &amp; Hoboken
            </div>
            <div style="height:1px; background:rgba(255,255,255,.2);
                        margin: 1rem 0;"></div>
            <div style="font-size:.7rem; color:rgba(255,255,255,.5);">
                Dec 2024 – Jan 2026 · 1,093,685 trips
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div style="margin-top:1rem;">
            <div style="font-size:.7rem; color:rgba(255,255,255,.5);
                        text-transform:uppercase; letter-spacing:.1em; margin-bottom:.5rem;">
                Navigation
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Landing page content ──────────────────────────────────────────────
st.markdown(
    f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['secondary']} 100%);
        border-radius: 16px;
        padding: 2.5rem 3rem;
        color: white;
        margin-bottom: 2rem;
    ">
        <h1 style="color:white; font-size:2.4rem; margin:0 0 .5rem 0;">
            🚲&nbsp; Citi Bike Analysis
        </h1>
        <p style="font-size:1.1rem; opacity:.9; margin:0;">
            Jersey City &amp; Hoboken · December 2024 – January 2026
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Trips", "1,093,685")
with col2:
    st.metric("Member Share", "78.4%")
with col3:
    st.metric("Electric Share", "64.6%")
with col4:
    st.metric("Stations", "112")
with col5:
    st.metric("Months Covered", "14")

st.markdown("---")
st.markdown("### 👈 Select a page from the sidebar to explore the data.")

st.markdown(
    """
    | Page | What you'll find |
    |---|---|
    | **1 · Overview** | KPIs, monthly ridership + MoM change, casual share trend |
    | **2 · Temporal** | Hour × day heatmap, hourly profiles with rush bands, seasonal & DoW |
    | **3 · Member vs Casual** | Duration, distance, speed, 4-panel behaviour grid, Mann-Whitney |
    | **4 · Stations** | Top stations, net flow, station explorer, network & trip-type analysis |
    | **5 · Map** | Geospatial trip origins (hexbin 3D) and station bubble map |
    | **6 · Rideable Type** | Electric vs classic — monthly share, hourly usage, duration, speed |
    | **7 · Weather** | Temp, rain, snow, wind impact on daily ridership (requires `daily_weather_merged.csv`) |
    """
)

st.markdown(
    f"<p style='color:{COLORS['muted']};font-size:.8rem;margin-top:2rem;'>"
    "Data sourced from Citi Bike official S3 bucket · Weather from NOAA NCEI (LaGuardia) · "
    "Analysis: Python 3.11 / pandas / plotly / pydeck</p>",
    unsafe_allow_html=True,
)
