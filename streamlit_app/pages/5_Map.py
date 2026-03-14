"""
pages/5_Map.py  –  Geospatial trip origins (hexbin) and station bubble map (pydeck)
"""

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (
    load_data, apply_global_css, page_header, callout,
    fmt_num, COLORS,
)

st.set_page_config(page_title="Map · Citi Bike", page_icon="🚲", layout="wide")
apply_global_css()

df = load_data()

page_header("Geospatial Map", "Trip origin density and station-level volume across Jersey City & Hoboken")

# ── SIDEBAR ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Map Controls")
    user_filter = st.selectbox(
        "User type", options=["All","member","casual"], index=0, key="map_user",
    )
    map_type = st.radio(
        "Map type",
        options=["Trip Origins (Hexbin)", "Station Bubbles"],
        index=0,
    )
    if map_type == "Trip Origins (Hexbin)":
        elevation_scale = st.slider("3D elevation scale", 1, 20, 6)
        radius = st.slider("Hex radius (metres)", 50, 300, 100, step=25)

# ── FILTER ────────────────────────────────────────────────────────────
dff = df if user_filter == "All" else df[df["member_casual"] == user_filter]

coord_cols = ["start_lat", "start_lng"]
if not all(c in dff.columns for c in coord_cols):
    st.error("Coordinate columns (start_lat, start_lng) not found in the dataset.")
    st.stop()

map_df = dff[coord_cols + ["member_casual","rideable_type"]].dropna(subset=coord_cols)
MAX_POINTS = 200_000
if len(map_df) > MAX_POINTS:
    map_df = map_df.sample(MAX_POINTS, random_state=42)
map_df = map_df.rename(columns={"start_lat": "lat", "start_lng": "lng"})

VIEW = pdk.ViewState(latitude=40.725, longitude=-74.045, zoom=12.5, pitch=45, bearing=0)

# ── HEXBIN MAP ────────────────────────────────────────────────────────
if map_type == "Trip Origins (Hexbin)":
    st.markdown(f"### Trip Origin Density — {user_filter} riders")
    st.caption(f"Showing {fmt_num(len(map_df))} trips (sampled from {fmt_num(len(dff))})")

    hex_layer = pdk.Layer(
        "HexagonLayer",
        data=map_df[["lat","lng"]],
        get_position=["lng","lat"],
        radius=radius,
        elevation_scale=elevation_scale,
        elevation_range=[0, 500],
        extruded=True, pickable=True, auto_highlight=True,
        color_range=[
            [235,245,255,80], [0,174,239,160],
            [0,85,165,200],   [0,31,77,220],
        ],
        coverage=0.85,
    )
    deck = pdk.Deck(
        layers=[hex_layer],
        initial_view_state=VIEW,
        tooltip={
            "html": "<b>Trips in hex:</b> {elevationValue}",
            "style": {"backgroundColor": "#0055A5", "color": "white", "fontSize": "13px"},
        },
        map_style="mapbox://styles/mapbox/light-v10",
    )
    st.pydeck_chart(deck, use_container_width=True, height=580)
    callout(
        "🗺 Taller/darker hexagons = more trip origins. "
        "PATH-station areas (Journal Square, Grove St, Exchange Place) and "
        "Hoboken Terminal corridor show the highest density."
    )

# ── STATION BUBBLES ───────────────────────────────────────────────────
else:
    st.markdown("### Station Bubble Map — Trip Volume & Casual Share")

    stn = (
        df.groupby("start_station_name", observed=True)
        .agg(
            trips      = ("ride_id","count"),
            casual_pct = ("member_casual", lambda x: (x=="casual").mean()*100),
            lat        = ("start_lat","median"),
            lng        = ("start_lng","median"),
        )
        .reset_index().dropna(subset=["lat","lng"])
    )
    MAX_R = 120
    stn["radius"] = (np.sqrt(stn["trips"]) / np.sqrt(stn["trips"].max()) * MAX_R).clip(lower=15)

    def pct_to_rgb(p):
        t = p / 100.0
        return [0, int(85 + t*(174-85)), int(165 + t*(239-165)), 200]

    stn["color"] = stn["casual_pct"].apply(pct_to_rgb)

    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=stn,
        get_position=["lng","lat"],
        get_radius="radius",
        get_fill_color="color",
        get_line_color=[255,255,255,120],
        line_width_min_pixels=1,
        pickable=True, auto_highlight=True,
    )
    VIEW_FLAT = pdk.ViewState(latitude=40.725, longitude=-74.045, zoom=12.5, pitch=0)
    deck2 = pdk.Deck(
        layers=[scatter_layer],
        initial_view_state=VIEW_FLAT,
        tooltip={
            "html": "<b>{start_station_name}</b><br>Trips: {trips}<br>Casual: {casual_pct:.1f}%",
            "style": {"backgroundColor": "#0055A5", "color": "white", "fontSize": "13px"},
        },
        map_style="mapbox://styles/mapbox/light-v10",
    )
    st.pydeck_chart(deck2, use_container_width=True, height=580)
    callout(
        "Bubble <strong>size</strong> = total trip volume. "
        "Bubble <strong>colour</strong>: deeper blue = member-heavy (commuter); "
        "lighter blue = casual-heavy (leisure/waterfront)."
    )

    display = (
        stn[["start_station_name","trips","casual_pct","lat","lng"]]
        .sort_values("trips", ascending=False)
        .rename(columns={"start_station_name":"Station","trips":"Trips","casual_pct":"Casual %"})
    )
    display["Trips"]    = display["Trips"].apply(fmt_num)
    display["Casual %"] = display["Casual %"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(display.reset_index(drop=True), use_container_width=True, height=320)
