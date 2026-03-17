"""
pages/2_Temporal.py  –  Day×Hour heatmap · Hourly profiles (with rush bands) · Seasonal · DoW
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (
    load_data, apply_global_css, page_header, callout,
    plotly_layout_defaults, COLORS,
)

st.set_page_config(page_title="Temporal · Citi Bike", page_icon="🚲", layout="wide")
apply_global_css()

df = load_data()

# ── SIDEBAR ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filters")
    user_opts = st.multiselect(
        "User type", options=["member", "casual"],
        default=["member", "casual"], key="temporal_user",
    )
    if not user_opts:
        user_opts = ["member", "casual"]

dff = df[df["member_casual"].isin(user_opts)]

page_header("Temporal Patterns", "Hourly, daily, and seasonal demand analysis")

# ── DAY × HOUR HEATMAP ───────────────────────────────────────────────
st.markdown("### Demand Heatmap — Day of Week × Hour")

DAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

heatmap_pivot = (
    dff.groupby(["day_name", "hour"])
    .size().unstack(fill_value=0).reindex(DAY_ORDER)
)

hour_labels = [f"{h:02d}:00" for h in heatmap_pivot.columns]
customdata = np.tile(hour_labels, (len(heatmap_pivot), 1))

fig_heat = go.Figure(go.Heatmap(
    z=heatmap_pivot.values,
    x=list(heatmap_pivot.columns),
    y=list(heatmap_pivot.index),
    customdata=customdata,
    colorscale=[
        [0.0, "#EBF4FF"],
        [0.3, COLORS["secondary"]],
        [0.7, COLORS["primary"]],
        [1.0, "#001F4D"],
    ],
    hovertemplate="<b>%{y}</b> at %{customdata}<br>Trips: %{z:,}<extra></extra>",
    colorbar=dict(title="Trips", tickformat=","),
))
fig_heat.update_layout(title="Total Trips by Day and Hour")
fig_heat.update_xaxes(
    title="Hour of Day", tickmode="array",
    tickvals=list(range(0, 24)),
    ticktext=[f"{h:02d}:00" if h % 3 == 0 else "" for h in range(24)],
)
plotly_layout_defaults(fig_heat, height=360)
st.plotly_chart(fig_heat, use_container_width=True)

callout(
    "🗓 <strong>Weekdays</strong>: classic dual-peak commuter pattern (8–9 am, 5–6 pm). "
    "<strong>Weekends</strong>: broad midday peak (11 am–3 pm), no commuter spikes. "
    "Wednesday & Thursday are consistently the busiest weekdays."
)

st.markdown("---")

# ── HOURLY PROFILES with rush-hour bands ─────────────────────────────
st.markdown("### Hourly Profiles — Weekday vs Weekend")
st.caption("Shaded bands show AM rush (7–9:30) and PM rush (17–19:30)")

hourly = (
    dff.groupby(["hour", "is_weekend", "member_casual"], observed=True)
    .size().reset_index(name="trips")
)
hourly["day_type"] = hourly["is_weekend"].map({True: "Weekend", False: "Weekday"})

col1, col2 = st.columns(2)
for col, day_type in zip([col1, col2], ["Weekday", "Weekend"]):
    sub = hourly[hourly["day_type"] == day_type]

    fig = go.Figure()
    y_max = sub["trips"].max() * 1.15

    # Rush-hour shaded bands (weekday only)
    if day_type == "Weekday":
        for x0, x1, label, lx in [(7, 9.5, "AM rush", 7.15), (17, 19.5, "PM rush", 17.15)]:
            fig.add_vrect(
                x0=x0, x1=x1,
                fillcolor="rgba(0,85,165,0.07)",
                layer="below", line_width=0,
            )
            fig.add_annotation(
                x=lx, y=y_max * 0.95, text=label,
                showarrow=False, font=dict(size=10, color=COLORS["muted"]),
                xanchor="left",
            )

    for user, colour in [("member", COLORS["member"]), ("casual", COLORS["casual"])]:
        row = sub[sub["member_casual"] == user]
        fig.add_trace(go.Scatter(
            x=row["hour"], y=row["trips"],
            mode="lines+markers",
            name=user.title(),
            line=dict(color=colour, width=2.5),
            marker=dict(size=5),
            hovertemplate=f"<b>{user.title()}</b><br>Hour %{{x}}:00<br>Trips: %{{y:,}}<extra></extra>",
        ))

    fig.update_layout(
        title=day_type,
        xaxis=dict(title="Hour", tickmode="linear", dtick=3),
        yaxis=dict(title="Trips", tickformat=","),
    )
    plotly_layout_defaults(fig, height=340)
    col.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── SEASONAL BREAKDOWN ────────────────────────────────────────────────
st.markdown("### Seasonal Breakdown")

SEASON_ORDER = ["Winter","Spring","Summer","Fall"]

season_data = (
    dff.groupby(["season", "member_casual"], observed=True)
    .size().reset_index(name="trips")
)
season_data["season"] = pd.Categorical(season_data["season"], categories=SEASON_ORDER, ordered=True)
season_data = season_data.sort_values("season")

fig_season = px.bar(
    season_data, x="season", y="trips", color="member_casual", barmode="group",
    color_discrete_map={"member": COLORS["member"], "casual": COLORS["casual"]},
    labels={"season": "", "trips": "Trips", "member_casual": ""},
    title="Trip Volume by Season and User Type",
)
fig_season.update_traces(marker_line_width=0)
fig_season.update_yaxes(tickformat=",")
plotly_layout_defaults(fig_season, height=360)
st.plotly_chart(fig_season, use_container_width=True)

callout(
    "🌡 <strong>Summer</strong> dominates. "
    "Casual riders are more seasonally sensitive — their share rises sharply in Summer "
    "and collapses in Winter."
)

st.markdown("---")

# ── DAY OF WEEK ───────────────────────────────────────────────────────
st.markdown("### Trips by Day of Week")

dow = (
    dff.groupby(["day_name", "member_casual"], observed=True)
    .size().reset_index(name="trips")
)
dow["day_name"] = pd.Categorical(dow["day_name"], categories=DAY_ORDER, ordered=True)
dow = dow.sort_values("day_name")

fig_dow = px.bar(
    dow, x="day_name", y="trips", color="member_casual", barmode="stack",
    color_discrete_map={"member": COLORS["member"], "casual": COLORS["casual"]},
    labels={"day_name": "", "trips": "Trips", "member_casual": ""},
    title="Total Trips by Day of Week",
)
fig_dow.update_traces(marker_line_width=0)
fig_dow.update_yaxes(tickformat=",")
plotly_layout_defaults(fig_dow, height=340)
st.plotly_chart(fig_dow, use_container_width=True)
