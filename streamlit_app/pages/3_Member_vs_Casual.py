"""
pages/3_Member_vs_Casual.py  –  Duration · Distance · Speed · Behaviour grid · Stats
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (
    load_data, apply_global_css, page_header, callout,
    plotly_layout_defaults, fmt_num, COLORS,
)

st.set_page_config(page_title="Member vs Casual · Citi Bike", page_icon="🚲", layout="wide")
apply_global_css()

df = load_data()
members = df[df["member_casual"] == "member"]
casuals = df[df["member_casual"] == "casual"]

page_header("Member vs Casual", "Behavioural comparison — duration, distance, speed, timing, geography")

# ── STAT CARDS ────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Member Trips",       fmt_num(len(members)), f"{len(members)/len(df)*100:.1f}% of total")
c2.metric("Casual Trips",       fmt_num(len(casuals)), f"{len(casuals)/len(df)*100:.1f}% of total")
c3.metric("Member Median Dur.", f"{members['duration_min'].median():.1f} min")
c4.metric("Casual Median Dur.", f"{casuals['duration_min'].median():.1f} min",
          f"{casuals['duration_min'].median()/members['duration_min'].median():.1f}× longer")

st.markdown("---")

# ── DURATION DISTRIBUTION ─────────────────────────────────────────────
st.markdown("### Trip Duration Distribution")

tabs = st.tabs(["Duration", "Distance", "Speed"])

with tabs[0]:
    col_hist, col_box = st.columns([3, 2])

    with col_hist:
        st.caption("Density histogram — capped at 60 min")
        fig_hist = go.Figure()
        for user, colour in [("member", COLORS["member"]), ("casual", COLORS["casual"])]:
            sub = df[(df["member_casual"] == user) & (df["duration_min"] <= 60)]["duration_min"]
            fig_hist.add_trace(go.Histogram(
                x=sub, nbinsx=60, name=user.title(),
                marker_color=colour, opacity=0.72,
                histnorm="probability density",
                hovertemplate=f"<b>{user.title()}</b><br>%{{x:.1f}} min<br>Density: %{{y:.4f}}<extra></extra>",
            ))
        fig_hist.update_layout(barmode="overlay", title="Duration Distribution (≤60 min, density-normalised)")
        fig_hist.update_xaxes(title="Duration (min)")
        fig_hist.update_yaxes(title="Density")
        plotly_layout_defaults(fig_hist, height=360)
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_box:
        st.caption("Duration by user & bike type (≤60 min)")
        # Box plot data
        bp = df[df["duration_min"] <= 60].copy()
        fig_box = px.box(
            bp, x="member_casual", y="duration_min", color="rideable_type",
            color_discrete_map={
                "electric_bike": COLORS["electric"],
                "classic_bike":  COLORS["classic"],
            },
            points=False,
            labels={"member_casual": "User Type", "duration_min": "Duration (min)", "rideable_type": ""},
            title="Duration by User & Bike Type",
        )
        plotly_layout_defaults(fig_box, height=360)
        st.plotly_chart(fig_box, use_container_width=True)

with tabs[1]:
    dist_df = df[df["distance_km"].notna() & (df["distance_km"] > 0)]

    col_dh, col_sc = st.columns(2)

    with col_dh:
        st.caption("Distance histogram — capped at 6 km")
        fig_dh = go.Figure()
        for user, colour in [("member", COLORS["member"]), ("casual", COLORS["casual"])]:
            sub = dist_df[dist_df["member_casual"] == user]["distance_km"].clip(upper=6)
            fig_dh.add_trace(go.Histogram(
                x=sub, nbinsx=60, name=user.title(),
                marker_color=colour, opacity=0.65, histnorm="probability density",
                hovertemplate=f"<b>{user.title()}</b><br>%{{x:.2f}} km<extra></extra>",
            ))
        fig_dh.update_layout(barmode="overlay", title="Trip Distance (≤6 km, density-normalised)")
        fig_dh.update_xaxes(title="Distance (km)")
        fig_dh.update_yaxes(title="Density")
        plotly_layout_defaults(fig_dh, height=360)
        st.plotly_chart(fig_dh, use_container_width=True)

    with col_sc:
        st.caption("Distance vs Duration — 5,000 trip sample (local trips ≤60 min)")
        sample = (
            dist_df[
                ~dist_df.get("is_cross_hudson", pd.Series(False, index=dist_df.index))
                & (dist_df["duration_min"] <= 60)
            ]
            .sample(min(5000, len(dist_df)), random_state=42)
        )
        fig_sc = px.scatter(
            sample, x="distance_km", y="duration_min", color="member_casual",
            color_discrete_map={"member": COLORS["member"], "casual": COLORS["casual"]},
            opacity=0.25, size_max=4,
            labels={"distance_km": "Distance (km)", "duration_min": "Duration (min)", "member_casual": ""},
            title="Distance vs Duration",
        )
        fig_sc.update_traces(marker=dict(size=4))
        plotly_layout_defaults(fig_sc, height=360)
        st.plotly_chart(fig_sc, use_container_width=True)

    # Distance stats table
    st.markdown("**Distance statistics (km)**")
    st.dataframe(
        dist_df.groupby("member_casual", observed=True)["distance_km"]
        .describe(percentiles=[.5, .75, .95]).round(3),
        use_container_width=True,
    )

with tabs[2]:
    speed_df = df[df["speed_kmh"].notna() & df["speed_kmh"].between(1, 40)]

    col_vio, col_spd = st.columns(2)

    with col_vio:
        st.caption("Speed distribution by user type and bike type")
        fig_vio = px.violin(
            speed_df, x="member_casual", y="speed_kmh", color="rideable_type",
            color_discrete_map={
                "electric_bike": COLORS["electric"],
                "classic_bike":  COLORS["classic"],
            },
            box=True, points=False,
            labels={"member_casual": "User Type", "speed_kmh": "Speed (km/h)", "rideable_type": ""},
            title="Speed by User & Bike Type",
        )
        plotly_layout_defaults(fig_vio, height=380)
        st.plotly_chart(fig_vio, use_container_width=True)

    with col_spd:
        st.caption("Median speed by hour of day (all trips)")
        hourly_speed = speed_df.groupby("hour")["speed_kmh"].median().reset_index()
        fig_spd = px.line(
            hourly_speed, x="hour", y="speed_kmh",
            markers=True,
            color_discrete_sequence=[COLORS["primary"]],
            labels={"hour": "Hour of Day", "speed_kmh": "Median Speed (km/h)"},
            title="Median Speed by Hour",
        )
        fig_spd.update_traces(line_width=2.5, marker_size=5)
        fig_spd.update_xaxes(tickmode="linear", dtick=2)
        plotly_layout_defaults(fig_spd, height=380)
        st.plotly_chart(fig_spd, use_container_width=True)

    callout(
        "⚡ Electric bikes show measurably higher median speeds than classic bikes. "
        "Speeds are highest in off-peak hours (less traffic, more confident riders)."
    )

st.markdown("---")

# ── BEHAVIOURAL PROFILE GRID (from notebook Cell 17) ─────────────────
st.markdown("### Behavioural Profile — 4-Panel Summary")

panel_col1, panel_col2 = st.columns(2)

# 1. Bike type preference %
with panel_col1:
    ride_pref = (
        df.groupby(["member_casual", "rideable_type"], observed=True)
        .size().unstack(fill_value=0)
    )
    ride_pct = (ride_pref.div(ride_pref.sum(axis=1), axis=0) * 100).reset_index()
    ride_melt = ride_pct.melt(id_vars="member_casual", var_name="bike", value_name="pct")
    fig_bp = px.bar(
        ride_melt, x="member_casual", y="pct", color="bike", barmode="group",
        color_discrete_map={
            "electric_bike": COLORS["electric"],
            "classic_bike":  COLORS["classic"],
            "docked_bike":   COLORS["muted"],
        },
        labels={"member_casual": "", "pct": "%", "bike": ""},
        title="Bike Type Preference (%)",
    )
    fig_bp.update_traces(marker_line_width=0)
    fig_bp.update_xaxes(tickmode="array", tickvals=["member","casual"], ticktext=["Member","Casual"])
    plotly_layout_defaults(fig_bp, height=300)
    panel_col1.plotly_chart(fig_bp, use_container_width=True)

# 2. Weekend share %
with panel_col2:
    wknd = (
        df.groupby(["member_casual", "is_weekend"], observed=True)
        .size().unstack(fill_value=0)
    )
    wknd_pct = (wknd.div(wknd.sum(axis=1), axis=0) * 100)
    wknd_pct.columns = ["Weekday","Weekend"]
    wknd_melt = wknd_pct.reset_index().melt(id_vars="member_casual", var_name="day_type", value_name="pct")
    fig_wk = px.bar(
        wknd_melt, x="member_casual", y="pct", color="day_type", barmode="group",
        color_discrete_map={"Weekday": COLORS["primary"], "Weekend": COLORS["secondary"]},
        labels={"member_casual": "", "pct": "%", "day_type": ""},
        title="Weekend vs Weekday Share (%)",
    )
    fig_wk.update_traces(marker_line_width=0)
    plotly_layout_defaults(fig_wk, height=300)
    panel_col2.plotly_chart(fig_wk, use_container_width=True)

panel_col3, panel_col4 = st.columns(2)

# 3. Rush hour share %
with panel_col3:
    rush = (
        df.groupby(["member_casual", "is_rush"], observed=True)
        .size().unstack(fill_value=0)
    )
    rush_pct = (rush.div(rush.sum(axis=1), axis=0) * 100)
    rush_pct.columns = ["Off-peak","Rush hour"]
    rush_melt = rush_pct.reset_index().melt(id_vars="member_casual", var_name="timing", value_name="pct")
    fig_rh = px.bar(
        rush_melt, x="member_casual", y="pct", color="timing", barmode="group",
        color_discrete_map={"Rush hour": COLORS["accent"], "Off-peak": COLORS["secondary"]},
        labels={"member_casual": "", "pct": "%", "timing": ""},
        title="Rush Hour vs Off-Peak Share (%)",
    )
    fig_rh.update_traces(marker_line_width=0)
    plotly_layout_defaults(fig_rh, height=300)
    panel_col3.plotly_chart(fig_rh, use_container_width=True)

# 4. Season distribution %
with panel_col4:
    SEASON_ORDER = ["Winter","Spring","Summer","Fall"]
    season_split = (
        df.groupby(["member_casual", "season"], observed=True)
        .size().unstack(fill_value=0)
    )
    season_pct = (season_split.div(season_split.sum(axis=1), axis=0) * 100)
    available_seasons = [s for s in SEASON_ORDER if s in season_pct.columns]
    season_melt = season_pct[available_seasons].reset_index().melt(
        id_vars="member_casual", var_name="season", value_name="pct"
    )
    season_melt["season"] = pd.Categorical(season_melt["season"], categories=SEASON_ORDER, ordered=True)
    fig_ss = px.bar(
        season_melt, x="member_casual", y="pct", color="season", barmode="group",
        color_discrete_map={
            "Winter": "#5B9BD5", "Spring": "#70AD47",
            "Summer": COLORS["electric"], "Fall": "#ED7D31",
        },
        labels={"member_casual": "", "pct": "%", "season": ""},
        title="Season Distribution (%)",
    )
    fig_ss.update_traces(marker_line_width=0)
    plotly_layout_defaults(fig_ss, height=300)
    panel_col4.plotly_chart(fig_ss, use_container_width=True)

st.markdown("---")

# ── STATISTICAL TEST ──────────────────────────────────────────────────
st.markdown("### Statistical Tests")

member_dur = members["duration_min"].dropna()
casual_dur = casuals["duration_min"].dropna()

SAMPLE = 100_000
if len(member_dur) > SAMPLE:
    md_s = member_dur.sample(SAMPLE, random_state=42)
    cd_s = casual_dur.sample(SAMPLE, random_state=42)
else:
    md_s, cd_s = member_dur, casual_dur

u_stat, pval = stats.mannwhitneyu(md_s, cd_s, alternative="two-sided")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Test",        "Mann-Whitney U")
c2.metric("U Statistic", f"{u_stat:,.0f}")
c3.metric("p-value",     "< 0.0001" if pval < 0.0001 else f"{pval:.4f}")
c4.metric("Result",      "Significant ✓" if pval < 0.05 else "Not significant")

callout(
    "Mann-Whitney U was chosen over a t-test because trip duration is heavily right-skewed. "
    "With 1.09 M observations the test has effectively infinite power; "
    "p &lt; 0.0001 confirms the duration difference is real, not a sample-size artefact."
)
