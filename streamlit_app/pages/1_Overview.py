"""
pages/1_Overview.py  –  KPIs · Monthly ridership · MoM change · Casual share trend · Summary table
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

st.set_page_config(page_title="Overview · Citi Bike", page_icon="🚲", layout="wide")
apply_global_css()

df = load_data()

# ── KPI CARDS ────────────────────────────────────────────────────────
page_header("Overview", "High-level snapshot of the full 14-month dataset")

total        = len(df)
member_pct   = (df["member_casual"] == "member").mean() * 100
electric_pct = (df["rideable_type"] == "electric_bike").mean() * 100
med_dur      = df["duration_min"].median()
cross_hudson = int(df["is_cross_hudson"].sum()) if "is_cross_hudson" in df.columns else 0
n_stations   = df["start_station_name"].nunique()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Trips",     fmt_num(total))
c2.metric("Member Share",    f"{member_pct:.1f}%")
c3.metric("Electric Share",  f"{electric_pct:.1f}%")
c4.metric("Median Duration", f"{med_dur:.1f} min")
c5.metric("Unique Stations", fmt_num(n_stations))
c6.metric("Cross-Hudson",    fmt_num(cross_hudson))

st.markdown("---")

# ── MONTHLY RIDERSHIP — local vs cross-Hudson ────────────────────────
page_header("Monthly Ridership", "Local trips vs cross-Hudson (→ NYC) trips")

monthly_base = df[df["month"] >= "2024-12"].copy()

if "is_cross_hudson" in monthly_base.columns:
    monthly_ch = (
        monthly_base
        .groupby(["month", "is_cross_hudson"], observed=True)
        .size().reset_index(name="trips")
    )
    monthly_ch["trip_class"] = monthly_ch["is_cross_hudson"].map(
        {False: "Local (JC+HB)", True: "Cross-Hudson (→ NYC)"}
    )
    fig_monthly = px.bar(
        monthly_ch, x="month", y="trips", color="trip_class",
        color_discrete_map={
            "Local (JC+HB)":        COLORS["primary"],
            "Cross-Hudson (→ NYC)": COLORS["accent"],
        },
        barmode="stack",
        labels={"month": "", "trips": "Trips", "trip_class": ""},
        title="Monthly Trip Volume — Local vs Cross-Hudson",
    )
else:
    monthly_user = (
        monthly_base
        .groupby(["month", "member_casual"], observed=True)
        .size().reset_index(name="trips")
    )
    fig_monthly = px.bar(
        monthly_user, x="month", y="trips", color="member_casual",
        color_discrete_map={"member": COLORS["member"], "casual": COLORS["casual"]},
        barmode="stack",
        labels={"month": "", "trips": "Trips", "member_casual": ""},
        title="Monthly Trip Volume",
    )

fig_monthly.update_traces(marker_line_width=0)
fig_monthly.update_xaxes(tickangle=-40)
fig_monthly.update_yaxes(tickformat=",")
plotly_layout_defaults(fig_monthly, height=360)
st.plotly_chart(fig_monthly, use_container_width=True)

# ── MONTH-OVER-MONTH % CHANGE ────────────────────────────────────────
st.markdown("#### Month-over-Month Change (%)")

monthly_total = monthly_base.groupby("month").size().sort_index()
mom = monthly_total.pct_change().mul(100).dropna().reset_index()
mom.columns = ["month", "pct_change"]
mom["colour"] = mom["pct_change"].apply(lambda v: COLORS["positive"] if v >= 0 else COLORS["accent"])

fig_mom = go.Figure(go.Bar(
    x=mom["month"], y=mom["pct_change"],
    marker_color=mom["colour"], marker_line_width=0,
    hovertemplate="<b>%{x}</b><br>MoM: %{y:+.1f}%<extra></extra>",
))
fig_mom.add_hline(y=0, line_color=COLORS["muted"], line_width=1)
fig_mom.update_layout(title="Month-over-Month Ridership Change (%)")
fig_mom.update_xaxes(tickangle=-40)
plotly_layout_defaults(fig_mom, height=280)
st.plotly_chart(fig_mom, use_container_width=True)

callout(
    "📈 <strong>Peak:</strong> Sep 2025 — 115,258 trips. "
    "<strong>Winter floor:</strong> Feb 2025 — 45,044 trips (~3:1 seasonal amplitude). "
    "The sharpest MoM declines occur Oct→Nov and Jan→Feb as cold weather sets in."
)

st.markdown("---")

# ── CASUAL SHARE TREND LINE ──────────────────────────────────────────
page_header("Casual Rider Share Over Time")

monthly_split = (
    monthly_base
    .groupby(["month", "member_casual"], observed=True)
    .size().unstack(fill_value=0).sort_index().reset_index()
)
monthly_split["casual_pct"] = (
    monthly_split.get("casual", 0)
    / (monthly_split.get("member", 0) + monthly_split.get("casual", 0))
    * 100
)
avg_pct = monthly_split["casual_pct"].mean()

fig_cas = go.Figure(go.Scatter(
    x=monthly_split["month"], y=monthly_split["casual_pct"],
    mode="lines+markers",
    line=dict(color=COLORS["casual"], width=2.5),
    marker=dict(size=6),
    fill="tozeroy",
    fillcolor="rgba(0,174,239,0.10)",
    hovertemplate="<b>%{x}</b><br>Casual: %{y:.1f}%<extra></extra>",
))
fig_cas.add_hline(
    y=avg_pct, line_dash="dash", line_color=COLORS["muted"],
    annotation_text=f"Avg {avg_pct:.1f}%", annotation_position="top right",
)
fig_cas.update_layout(title="Casual Rider Share by Month (%)")
fig_cas.update_yaxes(range=[0, 50], ticksuffix="%")
fig_cas.update_xaxes(tickangle=-40)
plotly_layout_defaults(fig_cas, height=280)
st.plotly_chart(fig_cas, use_container_width=True)

callout(
    "Casual share peaks in summer (potentially 25–30%) and collapses in winter (10–15%). "
    "This seasonal swing is larger than for members, who ride more consistently year-round."
)

st.markdown("---")

# ── BIKE TYPE BREAKDOWN ──────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    page_header("Bike Type Split")
    bike_counts = df["rideable_type"].value_counts().reset_index()
    bike_counts.columns = ["type", "count"]
    fig_bike = px.pie(
        bike_counts, names="type", values="count", color="type",
        color_discrete_map={
            "electric_bike": COLORS["electric"],
            "classic_bike":  COLORS["classic"],
            "docked_bike":   COLORS["muted"],
        },
        hole=0.55,
    )
    fig_bike.update_traces(textposition="outside", textinfo="percent+label")
    plotly_layout_defaults(fig_bike, height=320)
    fig_bike.update_layout(showlegend=False)
    st.plotly_chart(fig_bike, use_container_width=True)

with col_right:
    page_header("Bike Type × User Type")
    bike_user = (
        df.groupby(["member_casual", "rideable_type"], observed=True)
        .size().reset_index(name="trips")
    )
    bike_user["pct"] = bike_user.groupby("member_casual", observed=True)["trips"].transform(
        lambda x: x / x.sum() * 100
    )
    fig_bu = px.bar(
        bike_user, x="member_casual", y="pct", color="rideable_type",
        color_discrete_map={
            "electric_bike": COLORS["electric"],
            "classic_bike":  COLORS["classic"],
            "docked_bike":   COLORS["muted"],
        },
        barmode="stack",
        labels={"member_casual": "", "pct": "Share (%)", "rideable_type": ""},
        title="Bike Preference by User Type",
    )
    fig_bu.update_traces(marker_line_width=0)
    plotly_layout_defaults(fig_bu, height=320)
    st.plotly_chart(fig_bu, use_container_width=True)

st.markdown("---")

# ── SUMMARY TABLE ────────────────────────────────────────────────────
page_header("Summary Statistics by User Type")

rows = []
for user in ["member", "casual"]:
    sub = df[df["member_casual"] == user]
    rows.append({
        "User Type":       user.title(),
        "Trips":           fmt_num(len(sub)),
        "Share":           f"{len(sub)/total*100:.1f}%",
        "Median Duration": f"{sub['duration_min'].median():.1f} min",
        "Mean Duration":   f"{sub['duration_min'].mean():.1f} min",
        "Electric Share":  f"{(sub['rideable_type']=='electric_bike').mean()*100:.1f}%",
        "Weekend Share":   f"{sub['is_weekend'].mean()*100:.1f}%",
        "Rush Hour Share": f"{sub['is_rush'].mean()*100:.1f}%",
    })

st.dataframe(pd.DataFrame(rows).set_index("User Type"), use_container_width=True)
