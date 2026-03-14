"""
utils.py  –  Shared data loader, feature engineering, and design tokens
for the Citi Bike JC/Hoboken Streamlit dashboard.
"""

import os
import pandas as pd
import numpy as np
import streamlit as st

# ─────────────────────────────────────────────
#  DESIGN TOKENS  (Citi Bike brand palette)
# ─────────────────────────────────────────────
COLORS = {
    "primary":    "#0055A5",   # Citi Bike royal blue
    "secondary":  "#00AEEF",   # Citi sky blue
    "accent":     "#E31837",   # Citi red (used sparingly)
    "member":     "#0055A5",   # member series
    "casual":     "#00AEEF",   # casual series
    "electric":   "#F5A623",   # electric bike amber
    "classic":    "#6B7C93",   # classic bike slate
    "positive":   "#27AE60",
    "negative":   "#E31837",
    "bg":         "#F4F6FA",
    "card":       "#FFFFFF",
    "text":       "#1A2332",
    "muted":      "#6B7C93",
    "border":     "#DDE3EE",
}

PLOTLY_TEMPLATE = "plotly_white"

FONT_FAMILY = "Inter, 'Helvetica Neue', Arial, sans-serif"

# Discrete colour sequences reused across pages
SEQ_USER   = [COLORS["member"], COLORS["casual"]]
SEQ_BIKE   = [COLORS["electric"], COLORS["classic"]]
SEQ_SEASON = ["#0055A5", "#00AEEF", "#E31837", "#F5A623"]


# ─────────────────────────────────────────────
#  DATA LOADER  (cached – only runs once)
# ─────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "jc_trips_clean.csv")

@st.cache_data(show_spinner="Loading 1.09 M trips…")
def load_data() -> pd.DataFrame:
    """Load jc_trips_clean.csv, engineer features, and return the dataframe."""
    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["started_at", "ended_at"],
        dtype={
            "rideable_type":  "category",
            "member_casual":  "category",
            "start_station_name": "category",
            "end_station_name":   "category",
        },
        low_memory=False,
    )

    # ── Temporal features ──────────────────────────────────────────
    df["hour"]        = df["started_at"].dt.hour
    df["day_of_week"] = df["started_at"].dt.dayofweek          # 0=Mon
    df["day_name"]    = df["started_at"].dt.day_name()
    df["month"]       = df["started_at"].dt.to_period("M").astype(str)
    df["date"]        = df["started_at"].dt.normalize()
    df["is_weekend"]  = df["day_of_week"] >= 5
    df["is_rush"]     = df["hour"].isin(list(range(7, 10)) + list(range(17, 20)))

    month_num = df["started_at"].dt.month
    df["season"] = pd.cut(
        month_num,
        bins=[0, 2, 5, 8, 11, 12],
        labels=["Winter", "Spring", "Summer", "Fall", "Winter"],
        ordered=False,
    )
    # Fix December (month 12 → Winter)
    df.loc[month_num == 12, "season"] = "Winter"
    df["season"] = df["season"].astype("category")

    # ── Duration ──────────────────────────────────────────────────
    if "duration_sec" not in df.columns:
        df["duration_sec"] = (df["ended_at"] - df["started_at"]).dt.total_seconds()
    df["duration_min"] = df["duration_sec"] / 60.0

    # ── Geospatial features ────────────────────────────────────────
    if "distance_m" not in df.columns and all(
        c in df.columns for c in ["start_lat", "start_lng", "end_lat", "end_lng"]
    ):
        df["distance_m"]  = _haversine(
            df["start_lat"], df["start_lng"], df["end_lat"], df["end_lng"]
        )
        df["distance_km"] = df["distance_m"] / 1000.0

    if "speed_kmh" not in df.columns and "distance_km" in df.columns:
        mask = (df.get("distance_m", 0) > 50) & (df["duration_min"] > 1)
        df["speed_kmh"] = np.nan
        df.loc[mask, "speed_kmh"] = (
            df.loc[mask, "distance_km"] / (df.loc[mask, "duration_min"] / 60.0)
        )

    # ── Network / classification features ────────────────────────
    if "start_network" not in df.columns and "start_station_id" in df.columns:
        df["start_network"] = _network_flag(df["start_station_id"].astype(str))
        df["end_network"]   = _network_flag(df["end_station_id"].astype(str))

    if "is_cross_hudson" not in df.columns and "end_network" in df.columns:
        df["is_cross_hudson"] = df["end_network"] == "other"

    if "trip_type" not in df.columns and "start_network" in df.columns:
        df["trip_type"] = (
            df["start_network"].str.upper().str[:2]
            + "→"
            + df["end_network"].str.upper().str[:2]
        )
        df.loc[df["is_cross_hudson"], "trip_type"] = "→NYC"

    return df


def _haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    φ1, φ2 = np.radians(lat1), np.radians(lat2)
    dφ = np.radians(lat2 - lat1)
    dλ = np.radians(lon2 - lon1)
    a = np.sin(dφ / 2) ** 2 + np.cos(φ1) * np.cos(φ2) * np.sin(dλ / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _network_flag(station_id_series: pd.Series) -> pd.Series:
    s = station_id_series.str.upper()
    result = pd.Series("other", index=station_id_series.index, dtype="category")
    result[s.str.startswith("JC")] = "jersey_city"
    result[s.str.startswith("HB")] = "hoboken"
    return result


# ─────────────────────────────────────────────
#  SHARED UI HELPERS
# ─────────────────────────────────────────────
def apply_global_css():
    """Inject the dashboard-wide CSS."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: {FONT_FAMILY};
            color: {COLORS['text']};
        }}
        .main .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }}
        /* Metric cards */
        div[data-testid="metric-container"] {{
            background: {COLORS['card']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
            padding: 1rem 1.25rem;
            box-shadow: 0 1px 4px rgba(0,0,0,.06);
        }}
        div[data-testid="metric-container"] label {{
            color: {COLORS['muted']} !important;
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: .06em;
        }}
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
            font-size: 1.75rem !important;
            font-weight: 700 !important;
            color: {COLORS['primary']} !important;
        }}
        /* Section headers */
        h1 {{ color: {COLORS['primary']}; font-weight: 700; }}
        h2 {{ color: {COLORS['text']}; font-weight: 600; border-bottom: 2px solid {COLORS['secondary']}; padding-bottom: .3rem; }}
        h3 {{ color: {COLORS['text']}; font-weight: 600; }}
        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background: {COLORS['primary']};
        }}
        section[data-testid="stSidebar"] * {{
            color: #ffffff !important;
        }}
        section[data-testid="stSidebar"] .stSelectbox label,
        section[data-testid="stSidebar"] .stMultiSelect label {{
            color: rgba(255,255,255,.8) !important;
            font-size: .8rem;
            text-transform: uppercase;
            letter-spacing: .06em;
        }}
        /* Tabs */
        button[data-baseweb="tab"] {{
            font-weight: 600 !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {COLORS['primary']} !important;
            border-bottom-color: {COLORS['primary']} !important;
        }}
        /* Callout box */
        .cb-callout {{
            background: #EBF4FF;
            border-left: 4px solid {COLORS['primary']};
            border-radius: 6px;
            padding: .8rem 1rem;
            margin: .5rem 0 1rem 0;
            font-size: .9rem;
            color: {COLORS['text']};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def callout(text: str):
    st.markdown(f'<div class="cb-callout">{text}</div>', unsafe_allow_html=True)


def fmt_num(n, decimals=0) -> str:
    return f"{n:,.{decimals}f}"


def page_header(title: str, subtitle: str = ""):
    st.markdown(f"## {title}")
    if subtitle:
        st.markdown(f"<p style='color:{COLORS['muted']};margin-top:-.5rem'>{subtitle}</p>",
                    unsafe_allow_html=True)


def plotly_layout_defaults(fig, height=420):
    """Apply consistent layout to every Plotly figure."""
    fig.update_layout(
        height=height,
        template=PLOTLY_TEMPLATE,
        font_family=FONT_FAMILY,
        font_color=COLORS["text"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font_size=12,
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family=FONT_FAMILY,
        ),
        xaxis=dict(gridcolor=COLORS["border"], linecolor=COLORS["border"]),
        yaxis=dict(gridcolor=COLORS["border"], linecolor=COLORS["border"]),
    )
    return fig