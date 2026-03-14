"""
pages/6_Rideable_Type.py  –  Electric vs classic · Monthly share · Hourly usage · Duration · Speed
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (
    load_data, apply_global_css, page_header, callout,
    plotly_layout_defaults, fmt_num, COLORS,
)

st.set_page_config(page_title="Rideable Type · Citi Bike", page_icon="🚲", layout="wide")
apply_global_css()

df = load_data()

page_header("Rideable Type Analysis", "Electric vs classic bike patterns — monthly share, hourly usage, duration, speed")

# ── KPI CARDS ─────────────────────────────────────────────────────────
electric = df[df["rideable_type"] == "electric_bike"]
classic  = df[df["rideable_type"] == "classic_bike"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Electric Trips",    fmt_num(len(electric)))
c2.metric("Classic Trips",     fmt_num(len(classic)))
c3.metric("Electric Share",    f"{len(electric)/len(df)*100:.1f}%")
c4.metric("Elec. Median Dur.", f"{electric['duration_min'].median():.1f} min")
c5.metric("Class. Median Dur.",f"{classic['duration_min'].median():.1f} min")

st.markdown("---")

# ── MONTHLY ELECTRIC SHARE ────────────────────────────────────────────
page_header("Electric Share Over Time")

monthly_bike = (
    df[df["month"] >= "2024-12"]
    .groupby(["month","rideable_type"], observed=True)
    .size().unstack(fill_value=0)
)
monthly_bike_pct = monthly_bike.div(monthly_bike.sum(axis=1), axis=0) * 100
avg_elec = monthly_bike_pct["electric_bike"].mean()

fig_mshare = go.Figure()
fig_mshare.add_trace(go.Scatter(
    x=monthly_bike_pct.index,
    y=monthly_bike_pct["electric_bike"],
    mode="lines+markers",
    line=dict(color=COLORS["electric"], width=2.5),
    marker=dict(size=7),
    fill="tozeroy",
    fillcolor="rgba(245,166,35,0.12)",
    name="Electric %",
    hovertemplate="<b>%{x}</b><br>Electric share: %{y:.1f}%<extra></extra>",
))
fig_mshare.add_hline(
    y=avg_elec, line_dash="dash", line_color=COLORS["muted"],
    annotation_text=f"Avg {avg_elec:.1f}%", annotation_position="top right",
)
fig_mshare.update_layout(title="Electric Bike Share by Month (%)")
fig_mshare.update_yaxes(ticksuffix="%")
fig_mshare.update_xaxes(tickangle=-40)
plotly_layout_defaults(fig_mshare, height=300)
st.plotly_chart(fig_mshare, use_container_width=True)

st.markdown("---")

# ── HOURLY USAGE + DURATION SIDE BY SIDE ──────────────────────────────
page_header("Hourly Usage & Duration by Bike Type")

col1, col2 = st.columns(2)

with col1:
    hourly_bike = (
        df.groupby(["hour","rideable_type"], observed=True)
        .size().reset_index(name="trips")
    )
    hourly_bike = hourly_bike[hourly_bike["rideable_type"].isin(["electric_bike","classic_bike"])]

    fig_hourly = px.line(
        hourly_bike, x="hour", y="trips", color="rideable_type",
        color_discrete_map={
            "electric_bike": COLORS["electric"],
            "classic_bike":  COLORS["classic"],
        },
        markers=True,
        labels={"hour": "Hour of Day", "trips": "Trips", "rideable_type": ""},
        title="Hourly Trips by Bike Type",
    )
    fig_hourly.update_traces(line_width=2.5, marker_size=5)
    fig_hourly.update_xaxes(tickmode="linear", dtick=2)
    fig_hourly.update_yaxes(tickformat=",")
    plotly_layout_defaults(fig_hourly, height=360)
    st.plotly_chart(fig_hourly, use_container_width=True)

with col2:
    fig_dur = go.Figure()
    for bike, colour in [("electric_bike", COLORS["electric"]), ("classic_bike", COLORS["classic"])]:
        sub = df[df["rideable_type"] == bike]["duration_min"].clip(upper=45)
        fig_dur.add_trace(go.Histogram(
            x=sub, nbinsx=45, name=bike.replace("_", " ").title(),
            marker_color=colour, opacity=0.65, histnorm="probability density",
            hovertemplate=f"<b>{bike.replace('_',' ').title()}</b><br>%{{x:.1f}} min<extra></extra>",
        ))
    fig_dur.update_layout(
        barmode="overlay",
        title="Duration Distribution by Bike Type (≤45 min)",
        xaxis_title="Duration (min)", yaxis_title="Density",
    )
    plotly_layout_defaults(fig_dur, height=360)
    st.plotly_chart(fig_dur, use_container_width=True)

callout(
    "⚡ Electric bikes show a flatter duration distribution — riders use them for both short "
    "and longer trips. Classic bikes cluster more tightly around shorter trips, suggesting "
    "their use is more transactional."
)

st.markdown("---")

# ── ELECTRIC PREFERENCE BY USER TYPE × SEASON ─────────────────────────
page_header("Electric Preference by User Type & Season")

col3, col4 = st.columns(2)

with col3:
    user_bike = (
        df.groupby(["member_casual","rideable_type"], observed=True)
        .size().reset_index(name="trips")
    )
    user_bike["pct"] = user_bike.groupby("member_casual", observed=True)["trips"].transform(
        lambda x: x / x.sum() * 100
    )
    fig_ub = px.bar(
        user_bike[user_bike["rideable_type"].isin(["electric_bike","classic_bike"])],
        x="member_casual", y="pct", color="rideable_type", barmode="stack",
        color_discrete_map={
            "electric_bike": COLORS["electric"],
            "classic_bike":  COLORS["classic"],
        },
        labels={"member_casual": "User Type", "pct": "Share (%)", "rideable_type": ""},
        title="Bike Type Share by User Type (%)",
    )
    fig_ub.update_traces(marker_line_width=0)
    plotly_layout_defaults(fig_ub, height=340)
    st.plotly_chart(fig_ub, use_container_width=True)

with col4:
    SEASON_ORDER = ["Winter","Spring","Summer","Fall"]
    season_bike = (
        df[df["rideable_type"].isin(["electric_bike","classic_bike"])]
        .groupby(["season","rideable_type"], observed=True)
        .size().reset_index(name="trips")
    )
    season_bike["pct"] = season_bike.groupby("season", observed=True)["trips"].transform(
        lambda x: x / x.sum() * 100
    )
    season_bike["season"] = pd.Categorical(season_bike["season"], categories=SEASON_ORDER, ordered=True)
    season_bike = season_bike.sort_values("season")

    fig_sb = px.bar(
        season_bike, x="season", y="pct", color="rideable_type", barmode="stack",
        color_discrete_map={
            "electric_bike": COLORS["electric"],
            "classic_bike":  COLORS["classic"],
        },
        labels={"season": "", "pct": "Share (%)", "rideable_type": ""},
        title="Bike Type Share by Season (%)",
    )
    fig_sb.update_traces(marker_line_width=0)
    plotly_layout_defaults(fig_sb, height=340)
    st.plotly_chart(fig_sb, use_container_width=True)

st.markdown("---")

# ── DURATION & SPEED STATS TABLE ───────────────────────────────────────
page_header("Descriptive Statistics by Bike Type")

stats_rows = []
for bike in ["electric_bike","classic_bike"]:
    sub = df[df["rideable_type"] == bike]
    row = {
        "Bike Type":       bike.replace("_"," ").title(),
        "Trips":           fmt_num(len(sub)),
        "Share":           f"{len(sub)/len(df)*100:.1f}%",
        "Median Dur.":     f"{sub['duration_min'].median():.1f} min",
        "Mean Dur.":       f"{sub['duration_min'].mean():.1f} min",
        "Member Share":    f"{(sub['member_casual']=='member').mean()*100:.1f}%",
        "Weekend Share":   f"{sub['is_weekend'].mean()*100:.1f}%",
    }
    if "speed_kmh" in sub.columns:
        spd = sub["speed_kmh"].dropna()
        row["Median Speed"] = f"{spd.median():.1f} km/h" if len(spd) else "—"
    if "distance_km" in sub.columns:
        d = sub["distance_km"].dropna()
        row["Median Dist."] = f"{d.median():.2f} km" if len(d) else "—"
    stats_rows.append(row)

st.dataframe(pd.DataFrame(stats_rows).set_index("Bike Type"), use_container_width=True)
