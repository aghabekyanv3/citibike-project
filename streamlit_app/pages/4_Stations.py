"""
pages/4_Stations.py  –  Top stations · Net flow · Station explorer · Network & trip-type analysis
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
    plotly_layout_defaults, fmt_num, COLORS,
)

st.set_page_config(page_title="Stations · Citi Bike", page_icon="🚲", layout="wide")
apply_global_css()

df = load_data()

page_header("Station Analysis", "Top stations · net flow · station explorer · network & trip-type breakdown")

# ── SIDEBAR ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Controls")
    top_n = st.slider("Top N stations", 10, 30, 20, step=5)

# ── TRIP TYPE CLASSIFICATION ──────────────────────────────────────────
if "trip_type" not in df.columns and "start_network" in df.columns:
    def _trip_type(row):
        s = str(row["start_network"])
        e = str(row["end_network"])
        if s == "jersey_city" and e == "jersey_city": return "JC → JC"
        if s == "hoboken"     and e == "hoboken":      return "HB → HB"
        if s == "jersey_city" and e == "hoboken":      return "JC → HB"
        if s == "hoboken"     and e == "jersey_city":  return "HB → JC"
        return "Other"
    df["trip_type"] = df.apply(_trip_type, axis=1).astype("category")

# ── TABS ──────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Top Stations & Net Flow", "🔍 Station Explorer", "🗺 Network Analysis"])

# ═══════════════════════════════════════════════════
# TAB 1 — TOP STATIONS + NET FLOW
# ═══════════════════════════════════════════════════
with tab1:
    st.markdown("### Top Start Stations")

    start_counts = (
        df.groupby("start_station_name", observed=True)
        .agg(trips=("ride_id","count"), casual_pct=("member_casual", lambda x: (x=="casual").mean()*100))
        .reset_index().sort_values("trips", ascending=False).head(top_n)
    )

    fig_top = px.bar(
        start_counts.sort_values("trips"),
        x="trips", y="start_station_name", orientation="h",
        color="casual_pct",
        color_continuous_scale=[
            [0.0, COLORS["primary"]],
            [0.5, COLORS["secondary"]],
            [1.0, COLORS["electric"]],
        ],
        color_continuous_midpoint=start_counts["casual_pct"].median(),
        labels={"trips": "Total Trips", "start_station_name": "", "casual_pct": "Casual %"},
        title=f"Top {top_n} Start Stations (colour = casual rider share)",
    )
    fig_top.update_traces(marker_line_width=0)
    fig_top.update_xaxes(tickformat=",")
    plotly_layout_defaults(fig_top, height=max(400, top_n * 22))
    st.plotly_chart(fig_top, use_container_width=True)

    callout(
        "<strong>Deeper blue</strong> = member-heavy (commuter stations near PATH/ferry). "
        "<strong>Lighter/amber</strong> = casual-heavy (waterfront/leisure)."
    )

    st.markdown("---")
    st.markdown("### Station Net Flow (Departures − Arrivals)")

    departures = df.groupby("start_station_name", observed=True).size().rename("departures")
    valid_ends = df[df["end_station_name"].isin(departures.index)]
    arrivals   = valid_ends.groupby("end_station_name", observed=True).size().rename("arrivals")

    flow = pd.concat([departures, arrivals], axis=1).fillna(0)
    flow["net_flow"]    = flow["departures"] - flow["arrivals"]
    flow["total_trips"] = flow["departures"] + flow["arrivals"]

    top_imbalanced = (
        flow[flow["total_trips"] >= 500]
        .reindex(flow["net_flow"].abs().nlargest(20).index)
        .sort_values("net_flow")
    )

    fig_flow = go.Figure(go.Bar(
        x=top_imbalanced["net_flow"],
        y=top_imbalanced.index,
        orientation="h",
        marker_color=[COLORS["accent"] if v < 0 else COLORS["positive"] for v in top_imbalanced["net_flow"]],
        hovertemplate="<b>%{y}</b><br>Net flow: %{x:+,}<extra></extra>",
    ))
    fig_flow.add_vline(x=0, line_color=COLORS["muted"], line_width=1.5, line_dash="dot")
    fig_flow.update_layout(title="Top 20 Most Imbalanced Stations — Net Flow (departures − arrivals)")
    plotly_layout_defaults(fig_flow, height=520)
    st.plotly_chart(fig_flow, use_container_width=True)

    callout(
        "🔴 <strong>Red</strong> = net importer (bikes accumulate). "
        "🟢 <strong>Green</strong> = net exporter (bikes drain away). "
        "Transit hub stations typically drain in the AM and refill in the PM."
    )

# ═══════════════════════════════════════════════════
# TAB 2 — STATION EXPLORER
# ═══════════════════════════════════════════════════
with tab2:
    st.markdown("### Station Explorer")
    all_stations = sorted(df["start_station_name"].dropna().unique().tolist())
    selected = st.selectbox("Select a station", options=all_stations)

    if selected:
        stn_df = df[df["start_station_name"] == selected]

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Total Trips",    fmt_num(len(stn_df)))
        sc2.metric("Member Share",   f"{(stn_df['member_casual']=='member').mean()*100:.1f}%")
        sc3.metric("Casual Share",   f"{(stn_df['member_casual']=='casual').mean()*100:.1f}%")
        sc4.metric("Electric Share", f"{(stn_df['rideable_type']=='electric_bike').mean()*100:.1f}%")

        col_h, col_d = st.columns(2)

        with col_h:
            hrly = (
                stn_df.groupby(["hour","member_casual"], observed=True)
                .size().reset_index(name="trips")
            )
            fig_h = px.line(
                hrly, x="hour", y="trips", color="member_casual",
                color_discrete_map={"member": COLORS["member"], "casual": COLORS["casual"]},
                markers=True,
                labels={"hour": "Hour", "trips": "Trips", "member_casual": ""},
                title=f"Hourly Demand — {selected}",
            )
            fig_h.update_xaxes(tickmode="linear", dtick=3)
            plotly_layout_defaults(fig_h, height=320)
            st.plotly_chart(fig_h, use_container_width=True)

        with col_d:
            top_dest = (
                stn_df[stn_df["end_station_name"] != selected]
                .groupby("end_station_name", observed=True)
                .size().reset_index(name="trips")
                .sort_values("trips", ascending=False).head(10)
            )
            fig_d = px.bar(
                top_dest.sort_values("trips"),
                x="trips", y="end_station_name", orientation="h",
                labels={"trips": "Trips", "end_station_name": ""},
                title=f"Top 10 Destinations from {selected}",
            )
            fig_d.update_traces(marker_color=COLORS["secondary"], marker_line_width=0)
            fig_d.update_xaxes(tickformat=",")
            plotly_layout_defaults(fig_d, height=320)
            st.plotly_chart(fig_d, use_container_width=True)

        monthly_stn = (
            stn_df.groupby("month", observed=True).size()
            .reset_index(name="trips").sort_values("month")
        )
        fig_ms = px.bar(
            monthly_stn, x="month", y="trips",
            labels={"month": "", "trips": "Trips"},
            title=f"Monthly Trend — {selected}",
        )
        fig_ms.update_traces(marker_color=COLORS["primary"], marker_line_width=0)
        fig_ms.update_xaxes(tickangle=-40)
        fig_ms.update_yaxes(tickformat=",")
        plotly_layout_defaults(fig_ms, height=260)
        st.plotly_chart(fig_ms, use_container_width=True)

# ═══════════════════════════════════════════════════
# TAB 3 — NETWORK & TRIP TYPE ANALYSIS
# ═══════════════════════════════════════════════════
with tab3:
    st.markdown("### Trip Type Distribution")

    if "trip_type" in df.columns:
        col_pie, col_cross = st.columns(2)

        with col_pie:
            tt_counts = df["trip_type"].value_counts().reset_index()
            tt_counts.columns = ["trip_type", "count"]
            fig_pie = px.pie(
                tt_counts, names="trip_type", values="count",
                color_discrete_sequence=[
                    COLORS["primary"], COLORS["secondary"],
                    "#EF5350", COLORS["electric"], COLORS["muted"],
                ],
                hole=0.5,
                title="Trip Type Distribution",
            )
            fig_pie.update_traces(textinfo="percent+label", textposition="outside")
            plotly_layout_defaults(fig_pie, height=380)
            fig_pie.update_layout(showlegend=False)
            col_pie.plotly_chart(fig_pie, use_container_width=True)

        with col_cross:
            cross_df = df[df["trip_type"].isin(["JC → HB", "HB → JC"])]
            if len(cross_df) > 0:
                cross_hourly = (
                    cross_df.groupby(["hour","trip_type"], observed=True)
                    .size().reset_index(name="trips")
                )
                fig_cross = px.line(
                    cross_hourly, x="hour", y="trips", color="trip_type",
                    color_discrete_map={
                        "JC → HB": COLORS["primary"],
                        "HB → JC": COLORS["secondary"],
                    },
                    markers=True,
                    labels={"hour": "Hour of Day", "trips": "Trips", "trip_type": ""},
                    title="Cross-Network Trips by Hour (JC↔HB)",
                )
                fig_cross.update_traces(line_width=2.5, marker_size=5)
                fig_cross.update_xaxes(tickmode="linear", dtick=2)
                plotly_layout_defaults(fig_cross, height=380)
                col_cross.plotly_chart(fig_cross, use_container_width=True)

        callout(
            "JC→JC accounts for ~55% of trips, HB→HB for ~45%. "
            "Cross-network commuter flow (JC↔HB) is a distinct pattern visible in the hourly chart. "
            "The ~3,571 cross-Hudson trips (→ NYC) represent one-way commuters who dock in Manhattan."
        )

        # Trip type × user type breakdown
        st.markdown("#### Trip Type by User Type")
        tt_user = (
            df.groupby(["trip_type","member_casual"], observed=True)
            .size().reset_index(name="trips")
        )
        fig_tt_user = px.bar(
            tt_user, x="trip_type", y="trips", color="member_casual", barmode="group",
            color_discrete_map={"member": COLORS["member"], "casual": COLORS["casual"]},
            labels={"trip_type": "Trip Type", "trips": "Trips", "member_casual": ""},
            title="Trips by Network Route and User Type",
        )
        fig_tt_user.update_traces(marker_line_width=0)
        fig_tt_user.update_yaxes(tickformat=",")
        plotly_layout_defaults(fig_tt_user, height=360)
        st.plotly_chart(fig_tt_user, use_container_width=True)

    else:
        st.info("Trip type data not available — ensure `start_network` and `end_network` columns are present in jc_trips_clean.csv.")

    st.markdown("---")
    st.markdown("### End-Station Discrepancy")
    n_start = df["start_station_name"].nunique()
    n_end   = df["end_station_name"].nunique()
    end_only_n = n_end - n_start

    c1, c2, c3 = st.columns(3)
    c1.metric("Unique Start Stations", fmt_num(n_start))
    c2.metric("Unique End Stations",   fmt_num(n_end))
    c3.metric("End-Only (NYC) Stations", fmt_num(end_only_n))

    callout(
        f"Of the {fmt_num(n_end)} unique end-station names, {fmt_num(end_only_n)} never appear as a start station. "
        "These are NYC Citi Bike stations (Manhattan/Brooklyn) — identifiable by their street-intersection naming. "
        "They represent ~3,571 one-way cross-Hudson commuter trips (0.33% of the dataset)."
    )
