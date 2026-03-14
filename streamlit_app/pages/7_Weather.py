"""
pages/7_Weather.py  –  Weather impact on ridership — temperature, rain, snow, wind
Loads daily_weather_merged.csv (output of notebook cell 29).
Falls back to re-building the daily aggregate if the weather file isn't present yet.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (
    load_data, apply_global_css, page_header, callout,
    plotly_layout_defaults, fmt_num, COLORS,
)

st.set_page_config(page_title="Weather · Citi Bike", page_icon="🚲", layout="wide")
apply_global_css()

# ── LOAD WEATHER DATA ─────────────────────────────────────────────────
WEATHER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "daily_weather_merged.csv")

@st.cache_data(show_spinner="Loading weather data…")
def load_weather():
    if os.path.exists(WEATHER_PATH):
        dw = pd.read_csv(WEATHER_PATH, parse_dates=["date"])
        # Ensure boolean columns
        for col in ["is_rain", "is_snow"]:
            if col in dw.columns:
                dw[col] = dw[col].astype(bool)
        if "temp_category" not in dw.columns and "temp_avg" in dw.columns:
            dw["temp_category"] = pd.cut(
                dw["temp_avg"], bins=[-30, 0, 10, 20, 40],
                labels=["Freezing","Cold","Mild","Warm"]
            )
        return dw, True
    else:
        return None, False

dw, found = load_weather()

page_header("Weather Impact", "How temperature, rain and snow affect daily ridership")

if not found:
    st.warning(
        "⚠️ **`data/daily_weather_merged.csv` not found.** "
        "Run notebook cell 29 first to generate it, then reload this page."
    )

    # Offer a rebuild from trip data alone (no weather)
    if st.button("Build daily trip summary without weather data"):
        df = load_data()
        df["date"] = df["started_at"].dt.normalize()
        dw = (
            df.groupby("date")
            .agg(
                trips_total  = ("ride_id","count"),
                trips_member = ("member_casual", lambda x: (x=="member").sum()),
                trips_casual = ("member_casual", lambda x: (x=="casual").sum()),
                median_dur   = ("duration_min","median"),
            )
            .reset_index()
        )
        dw["casual_pct"] = dw["trips_casual"] / dw["trips_total"] * 100
        found = True   # we have trip-level data now, just no weather columns
    else:
        st.stop()

# ── KPI CARDS ─────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Days in Dataset", fmt_num(len(dw)))

if "is_rain" in dw.columns:
    c2.metric("Rainy Days",  fmt_num(int(dw["is_rain"].sum())))
if "is_snow" in dw.columns:
    c3.metric("Snowy Days",  fmt_num(int(dw["is_snow"].sum())))
if "temp_avg" in dw.columns:
    c4.metric("Avg Temp.",   f"{dw['temp_avg'].mean():.1f}°C")
    c5.metric("Temp. Range", f"{dw['temp_avg'].min():.1f}°C – {dw['temp_avg'].max():.1f}°C")

st.markdown("---")

# ── DAILY TRIP TREND ──────────────────────────────────────────────────
page_header("Daily Trip Volume Over Time")

fig_daily = go.Figure()
fig_daily.add_trace(go.Scatter(
    x=dw["date"], y=dw["trips_total"],
    mode="lines",
    line=dict(color=COLORS["primary"], width=1.5),
    name="All trips",
    hovertemplate="<b>%{x|%b %d, %Y}</b><br>Trips: %{y:,}<extra></extra>",
))

# Overlay rolling 7-day average
rolling = dw.set_index("date")["trips_total"].rolling(7, center=True).mean().reset_index()
fig_daily.add_trace(go.Scatter(
    x=rolling["date"], y=rolling["trips_total"],
    mode="lines",
    line=dict(color=COLORS["secondary"], width=2.5),
    name="7-day avg",
    hovertemplate="7-day avg: %{y:,.0f}<extra></extra>",
))

fig_daily.update_layout(title="Daily Trip Volume with 7-Day Rolling Average")
fig_daily.update_yaxes(tickformat=",", title="Trips")
fig_daily.update_xaxes(title="")
plotly_layout_defaults(fig_daily, height=320)
st.plotly_chart(fig_daily, use_container_width=True)

st.markdown("---")

if "temp_avg" in dw.columns:
    # ── TEMPERATURE SCATTER ───────────────────────────────────────────
    page_header("Temperature vs Daily Trips")

    col_sc, col_cat = st.columns(2)

    with col_sc:
        fig_tsc = px.scatter(
            dw.dropna(subset=["temp_avg"]),
            x="temp_avg", y="trips_total",
            color="temp_category" if "temp_category" in dw.columns else None,
            color_discrete_map={
                "Freezing": "#5B9BD5",
                "Cold":     COLORS["secondary"],
                "Mild":     COLORS["electric"],
                "Warm":     COLORS["accent"],
            },
            opacity=0.65,
            trendline="ols",
            labels={"temp_avg": "Avg Temperature (°C)", "trips_total": "Daily Trips", "temp_category": ""},
            title="Daily Trips vs Temperature",
        )
        fig_tsc.update_yaxes(tickformat=",")
        plotly_layout_defaults(fig_tsc, height=380)
        st.plotly_chart(fig_tsc, use_container_width=True)

    with col_cat:
        if "temp_category" in dw.columns:
            TEMP_ORDER = ["Freezing","Cold","Mild","Warm"]
            temp_agg = (
                dw.groupby("temp_category", observed=True)["trips_total"]
                .agg(["mean","median"]).round(0).reset_index()
            )
            temp_agg["temp_category"] = pd.Categorical(temp_agg["temp_category"], categories=TEMP_ORDER, ordered=True)
            temp_agg = temp_agg.sort_values("temp_category")

            fig_tcat = px.bar(
                temp_agg, x="temp_category", y="mean",
                color="temp_category",
                color_discrete_map={
                    "Freezing": "#5B9BD5", "Cold": COLORS["secondary"],
                    "Mild": COLORS["electric"], "Warm": COLORS["accent"],
                },
                labels={"temp_category": "", "mean": "Avg Daily Trips"},
                title="Avg Daily Trips by Temperature Category",
                error_y=None,
            )
            fig_tcat.update_traces(marker_line_width=0, showlegend=False)
            fig_tcat.update_yaxes(tickformat=",")
            plotly_layout_defaults(fig_tcat, height=380)
            st.plotly_chart(fig_tcat, use_container_width=True)

    callout(
        "🌡 Strong positive correlation between temperature and ridership. "
        "Warm days (>20°C) average ~2.5–3× more trips than Freezing days (<0°C)."
    )

    st.markdown("---")

if "is_rain" in dw.columns:
    # ── RAIN IMPACT ───────────────────────────────────────────────────
    page_header("Rain & Snow Impact")

    col_r, col_s = st.columns(2)

    with col_r:
        rain_agg = (
            dw.groupby("is_rain")["trips_total"]
            .agg(["mean","median","count"]).reset_index()
        )
        rain_agg["label"] = rain_agg["is_rain"].map({False: "No Rain", True: "Rain Day (>1mm)"})
        fig_rain = px.bar(
            rain_agg, x="label", y="mean",
            color="label",
            color_discrete_map={"No Rain": COLORS["primary"], "Rain Day (>1mm)": COLORS["secondary"]},
            labels={"label": "", "mean": "Avg Daily Trips"},
            title="Avg Daily Trips — Rain vs No Rain",
            text="mean",
        )
        fig_rain.update_traces(
            marker_line_width=0, showlegend=False,
            texttemplate="%{text:,.0f}", textposition="outside",
        )
        fig_rain.update_yaxes(tickformat=",")
        plotly_layout_defaults(fig_rain, height=340)
        st.plotly_chart(fig_rain, use_container_width=True)

    if "is_snow" in dw.columns:
        with col_s:
            snow_agg = (
                dw.groupby("is_snow")["trips_total"]
                .agg(["mean","median"]).reset_index()
            )
            snow_agg["label"] = snow_agg["is_snow"].map({False: "No Snow", True: "Snow Day"})
            fig_snow = px.bar(
                snow_agg, x="label", y="mean",
                color="label",
                color_discrete_map={"No Snow": COLORS["primary"], "Snow Day": "#90CAF9"},
                labels={"label": "", "mean": "Avg Daily Trips"},
                title="Avg Daily Trips — Snow vs No Snow",
                text="mean",
            )
            fig_snow.update_traces(
                marker_line_width=0, showlegend=False,
                texttemplate="%{text:,.0f}", textposition="outside",
            )
            fig_snow.update_yaxes(tickformat=",")
            plotly_layout_defaults(fig_snow, height=340)
            st.plotly_chart(fig_snow, use_container_width=True)

    # Rain box plot — member vs casual
    if "trips_member" in dw.columns and "trips_casual" in dw.columns:
        st.markdown("#### Rain Impact: Member vs Casual (daily trips)")

        rain_long = dw[["date","is_rain","trips_member","trips_casual"]].melt(
            id_vars=["date","is_rain"],
            value_vars=["trips_member","trips_casual"],
            var_name="user_type", value_name="trips",
        )
        rain_long["user_type"] = rain_long["user_type"].map(
            {"trips_member": "Member", "trips_casual": "Casual"}
        )
        rain_long["weather"] = rain_long["is_rain"].map({False: "No Rain", True: "Rain"})

        fig_rb = px.box(
            rain_long, x="weather", y="trips", color="user_type",
            color_discrete_map={"Member": COLORS["member"], "Casual": COLORS["casual"]},
            points=False,
            labels={"weather": "", "trips": "Daily Trips", "user_type": ""},
            title="Daily Trips Distribution — Rain vs No Rain by User Type",
        )
        fig_rb.update_yaxes(tickformat=",")
        plotly_layout_defaults(fig_rb, height=380)
        st.plotly_chart(fig_rb, use_container_width=True)

        callout(
            "Rain suppresses casual ridership more than member ridership — "
            "members (commuters) continue riding in wet weather while casual riders (leisure) stay home."
        )

    st.markdown("---")

if "wind_speed" in dw.columns:
    # ── WIND SPEED ────────────────────────────────────────────────────
    page_header("Wind Speed vs Ridership")

    fig_wind = px.scatter(
        dw.dropna(subset=["wind_speed"]),
        x="wind_speed", y="trips_total",
        opacity=0.55,
        trendline="ols",
        color_discrete_sequence=[COLORS["secondary"]],
        labels={"wind_speed": "Avg Wind Speed (km/h)", "trips_total": "Daily Trips"},
        title="Daily Trips vs Wind Speed",
    )
    fig_wind.update_yaxes(tickformat=",")
    plotly_layout_defaults(fig_wind, height=340)
    st.plotly_chart(fig_wind, use_container_width=True)

st.markdown("---")

# ── SUMMARY TABLE ─────────────────────────────────────────────────────
page_header("Daily Ridership Summary")

desc_cols = ["trips_total"]
if "trips_member" in dw.columns: desc_cols.append("trips_member")
if "trips_casual" in dw.columns: desc_cols.append("trips_casual")

st.dataframe(
    dw[desc_cols].describe(percentiles=[.25,.5,.75]).round(0),
    use_container_width=True,
)
