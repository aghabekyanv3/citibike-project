"""
pages/8_Rebalancing.py
======================
Interactive rebalancing analysis dashboard page.

Convention: net_flow = arrivals − departures
  positive → surplus → bikes accumulate → needs PICKUP
  negative → deficit → bikes drain      → needs DELIVERY

All numbers are daily averages.
Requires jc_trips_clean.csv and (optionally) daily_weather_merged.csv.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.spatial.distance import cdist
from scipy.optimize import linear_sum_assignment  # ← Hungarian algorithm
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (
    load_data, apply_global_css, page_header, callout,
    plotly_layout_defaults, fmt_num, COLORS,
)

st.set_page_config(
    page_title="Rebalancing · Citi Bike",
    page_icon="🚲",
    layout="wide",
)
apply_global_css()

# ── Design tokens ──────────────────────────────────────────────────────
C_SURPLUS = "#EF5350"   # red   — bikes accumulate → pickup needed
C_DEFICIT = "#2196F3"   # blue  — bikes drain      → delivery needed
SEASON_COLORS = {
    "Winter": "#5B9BD5",
    "Spring": "#70AD47",
    "Summer": "#EF5350",
    "Fall":   "#ED7D31",
}
SEASON_ORDER = ["Winter", "Spring", "Summer", "Fall"]

# ── Cached computation helpers ─────────────────────────────────────────
@st.cache_data(show_spinner="Computing net flow…")
def compute_flow(df):
    valid_stations = set(df["start_station_name"].dropna().unique())
    n_days     = df["date"].nunique()
    n_weekdays = df[df["is_weekend"] == False]["date"].nunique()
    n_weekends = df[df["is_weekend"] == True]["date"].nunique()

    dep_total = df.groupby("start_station_name", observed=True).size().rename("dep_total")
    arr_total = (df[df["end_station_name"].isin(valid_stations)]
                 .groupby("end_station_name", observed=True).size().rename("arr_total"))
    flow = pd.concat([dep_total, arr_total], axis=1).fillna(0)
    flow["net_total"]     = flow["arr_total"] - flow["dep_total"]
    flow["total_trips"]   = flow["arr_total"] + flow["dep_total"]
    flow["net_per_day"]   = (flow["net_total"] / n_days).round(2)
    flow["dep_per_day"]   = (flow["dep_total"] / n_days).round(2)
    flow["arr_per_day"]   = (flow["arr_total"] / n_days).round(2)
    flow["imbalance_pct"] = (flow["net_total"].abs() / flow["total_trips"] * 100).round(1)

    dep_wd = (df[df["is_weekend"] == False]
              .groupby("start_station_name", observed=True).size().rename("dep_wd"))
    arr_wd = (df[(df["is_weekend"] == False) & df["end_station_name"].isin(valid_stations)]
              .groupby("end_station_name", observed=True).size().rename("arr_wd"))
    flow_wd = pd.concat([dep_wd, arr_wd], axis=1).fillna(0)
    flow["net_per_weekday"] = ((flow_wd["arr_wd"] - flow_wd["dep_wd"]) / n_weekdays).round(2)

    coords = (df.groupby("start_station_name", observed=True)
              .agg(lat=("start_lat", "median"), lng=("start_lng", "median")))
    flow = flow.join(coords)
    flow = flow[flow["total_trips"] >= 200].copy()
    return flow, valid_stations, n_days, n_weekdays, n_weekends


@st.cache_data(show_spinner="Building hourly profiles…")
def compute_hourly(df, valid_stations, n_weekdays, season=None):
    mask = df["is_weekend"] == False
    if season:
        mask = mask & (df["season"] == season)
    df_sub = df[mask].copy()
    n = df_sub["date"].nunique()
    if n == 0:
        return pd.DataFrame()
    dep = (df_sub.groupby(["start_station_name", "hour"], observed=True)
           .size().reset_index(name="dep_total"))
    arr = (df_sub[df_sub["end_station_name"].isin(valid_stations)]
           .groupby(["end_station_name", "hour"], observed=True)
           .size().reset_index(name="arr_total")
           .rename(columns={"end_station_name": "start_station_name"}))
    h = pd.merge(dep, arr, on=["start_station_name", "hour"], how="outer").fillna(0)
    h["net_avg"] = (h["arr_total"] - h["dep_total"]) / n
    h = h.sort_values(["start_station_name", "hour"])
    h["cumulative_avg"] = (h.groupby("start_station_name", observed=True)["net_avg"]
                           .cumsum())
    return h


@st.cache_data(show_spinner="Building season flow…")
def compute_season_flow(df, valid_stations, flow_base, season):
    df_s = df[(df["season"] == season) & (df["is_weekend"] == False)]
    n = df_s["date"].nunique()
    if n == 0:
        return None
    dep = df_s.groupby("start_station_name", observed=True).size().rename("dep_total")
    arr = (df_s[df_s["end_station_name"].isin(valid_stations)]
           .groupby("end_station_name", observed=True).size().rename("arr_total"))
    f = pd.concat([dep, arr], axis=1).fillna(0)
    f["net_per_day"]   = (f["arr_total"] - f["dep_total"]) / n
    f["total_trips"]   = flow_base["total_trips"]
    f["imbalance_pct"] = (f["net_per_day"].abs() /
                          (f["dep_total"] + f["arr_total"]).replace(0, np.nan) * 100).round(1)
    for col in ["lat", "lng"]:
        if col in flow_base.columns:
            f[col] = flow_base[col]
    f = f[f["total_trips"].notna() & (f["total_trips"] >= 200)]
    return f


def build_schedule(hourly_df, flow_df):
    rows = []
    for station in flow_df.index:
        sub = hourly_df[hourly_df["start_station_name"] == station]
        if sub.empty:
            continue
        net_daily = flow_df.loc[station, "net_per_day"]
        cum = sub.set_index("hour")["cumulative_avg"]
        if net_daily > 0:
            peak_hour = int(cum.idxmax())
            severity  = float(cum.max())
            role      = "pickup"
        else:
            peak_hour = int(cum.idxmin())
            severity  = float(abs(cum.min()))
            role      = "delivery"
        rows.append({
            "station":       station,
            "role":          role,
            "net_per_day":   round(net_daily, 2),
            "severity":      round(severity, 2),
            "action_by":     f"{peak_hour:02d}:00",
            "action_hour":   peak_hour,
            "total_trips":   int(flow_df.loc[station, "total_trips"]),
            "imbalance_pct": float(flow_df.loc[station, "imbalance_pct"]),
            "lat":           float(flow_df.loc[station, "lat"]) if "lat" in flow_df.columns else None,
            "lng":           float(flow_df.loc[station, "lng"]) if "lng" in flow_df.columns else None,
        })
    return (pd.DataFrame(rows).sort_values("severity", ascending=False)
            .reset_index(drop=True))


# ══════════════════════════════════════════════════════════════════════
# LOAD
# ══════════════════════════════════════════════════════════════════════
df = load_data()

if "season" not in df.columns:
    def _season(dt):
        m = dt.month
        if m in (12,1,2): return "Winter"
        if m in (3,4,5):  return "Spring"
        if m in (6,7,8):  return "Summer"
        return "Fall"
    df["season"] = df["started_at"].apply(_season)

flow, valid_stations, n_days, n_weekdays, n_weekends = compute_flow(df)
hourly_all = compute_hourly(df, valid_stations, n_weekdays)

page_header(
    "Rebalancing Analysis",
    "Station-level surplus & deficit — daily averages, by season  "
    "| Convention: net flow = arrivals − departures "
    "| 🔴 surplus = pickup needed  | 🔵 deficit = delivery needed",
)

# ── SIDEBAR ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Controls")
    season_sel = st.selectbox(
        "Season", options=["All seasons"] + SEASON_ORDER, index=0
    )
    top_n = st.slider("Top N stations", 10, 30, 20, step=5)
    show_weather = st.checkbox("Show weather section", value=True)

# Resolve selected flow and hourly
if season_sel == "All seasons":
    flow_sel   = flow
    hourly_sel = hourly_all
    season_label = "All seasons"
else:
    flow_s = compute_season_flow(df, valid_stations, flow, season_sel)
    if flow_s is None:
        st.warning(f"No weekday data for {season_sel}.")
        st.stop()
    flow_sel   = flow_s
    hourly_sel = compute_hourly(df, valid_stations, n_weekdays, season=season_sel)
    season_label = season_sel

schedule = build_schedule(hourly_sel, flow_sel)

# ══════════════════════════════════════════════════════════════════════
# KPI CARDS
# ══════════════════════════════════════════════════════════════════════
surplus_stns = int((flow_sel["net_per_day"] >  0.5).sum())
deficit_stns = int((flow_sel["net_per_day"] < -0.5).sum())
balanced_stns= int((flow_sel["net_per_day"].abs() <= 0.5).sum())
worst_surplus= flow_sel.nlargest(1,  "net_per_day").iloc[0]
worst_deficit= flow_sel.nsmallest(1, "net_per_day").iloc[0]

pickup_sched   = schedule[schedule["role"] == "pickup"]
delivery_sched = schedule[schedule["role"] == "delivery"]
total_surplus  = pickup_sched["net_per_day"].sum()
total_deficit  = delivery_sched["net_per_day"].sum()

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Surplus stations",  fmt_num(surplus_stns),  "need pickup")
c2.metric("Deficit stations",  fmt_num(deficit_stns),  "need delivery")
c3.metric("Balanced",          fmt_num(balanced_stns), "±0.5/day")
c4.metric("Worst surplus",     worst_surplus.name[:22], f"{worst_surplus['net_per_day']:+.1f}/day")
c5.metric("Worst deficit",     worst_deficit.name[:22], f"{worst_deficit['net_per_day']:+.1f}/day")
c6.metric("Net system imbal.", f"{total_surplus+total_deficit:+.1f} bikes/day")

callout(
    f"<strong>Convention:</strong> net flow = arrivals − departures. "
    f"🔴 Positive = surplus (bikes pile up, pickup needed). "
    f"🔵 Negative = deficit (bikes drain, delivery needed). "
    f"All values are daily averages — <strong>{season_label}</strong>."
)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Net Flow",
    "⏱ Hourly Cumulative",
    "🗓 Weekday vs Weekend",
    "🚲 Segments",
    "📅 Priority Schedule",
    "🗺 Pairing Map",
])

# ══════════════════════════════════════════════════════════════════════
# TAB 1 — NET FLOW
# ══════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(f"### Station Net Flow — {season_label}")
    st.caption("arrivals − departures per day  |  🔴 surplus (pickup)  |  🔵 deficit (delivery)")

    top_imb = (flow_sel.reindex(flow_sel["net_per_day"].abs().nlargest(top_n).index)
               .sort_values("net_per_day"))

    fig_nf = go.Figure(go.Bar(
        x=top_imb["net_per_day"],
        y=top_imb.index,
        orientation="h",
        marker_color=[C_SURPLUS if v > 0 else C_DEFICIT for v in top_imb["net_per_day"]],
        marker_line_width=0,
        text=[f"{v:+.1f}/day" for v in top_imb["net_per_day"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Net: %{x:+.2f} bikes/day<extra></extra>",
    ))
    fig_nf.add_vline(x=0, line_color="black", line_width=1)
    fig_nf.update_layout(
        title=f"Top {top_n} Most Imbalanced Stations — {season_label}",
        xaxis_title="Avg net flow per day (arrivals − departures)",
    )
    plotly_layout_defaults(fig_nf, height=max(500, top_n * 24))
    st.plotly_chart(fig_nf, use_container_width=True)

    # Seasonal comparison for same stations
    if season_sel == "All seasons":
        st.markdown("#### Seasonal Breakdown — Top 15 Stations")
        top15 = flow["net_per_day"].abs().nlargest(15).index
        season_traces = []
        for s in SEASON_ORDER:
            fs = compute_season_flow(df, valid_stations, flow, s)
            if fs is None:
                continue
            vals = fs.reindex(top15)["net_per_day"].fillna(0)
            season_traces.append(
                go.Bar(name=s, x=top15, y=vals,
                       marker_color=SEASON_COLORS[s], opacity=0.85)
            )
        fig_seas = go.Figure(data=season_traces)
        fig_seas.update_layout(
            barmode="group",
            title="Net Flow by Season — Top 15 Stations",
            xaxis_tickangle=-40,
            yaxis_title="Avg net flow per day",
        )
        plotly_layout_defaults(fig_seas, height=420)
        st.plotly_chart(fig_seas, use_container_width=True)

        callout(
            "Switch the <strong>Season</strong> selector in the sidebar to see "
            "station-specific daily averages for a single season."
        )


# ══════════════════════════════════════════════════════════════════════
# TAB 2 — HOURLY CUMULATIVE
# ══════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(f"### Cumulative Hourly Flow — Average Weekday ({season_label})")
    st.caption(
        "Shows when each station tips into surplus or deficit during the day. "
        "Values = avg bikes above/below starting balance at that hour."
    )

    focus_stations = flow_sel["net_per_day"].abs().nlargest(10).index.tolist()
    station_sel2 = st.selectbox(
        "Station to highlight",
        options=focus_stations,
        index=0,
        key="hourly_stn",
    )

    # Single station detail chart
    sub_stn = hourly_sel[hourly_sel["start_station_name"] == station_sel2]
    if not sub_stn.empty:
        net_d = flow_sel.loc[station_sel2, "net_per_day"] if station_sel2 in flow_sel.index else 0
        color = C_SURPLUS if net_d > 0 else C_DEFICIT

        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=sub_stn["hour"], y=sub_stn["cumulative_avg"],
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            name="Cumulative net",
            hovertemplate="Hour %{x}:00<br>Cumulative: %{y:+.2f} bikes<extra></extra>",
        ))
        fig_cum.add_hline(y=0, line_color="black", line_width=1, line_dash="dash")
        fig_cum.add_hrect(
            y0=0, y1=sub_stn["cumulative_avg"].max() * 1.1 or 1,
            fillcolor=C_SURPLUS, opacity=0.06, layer="below", line_width=0,
        )
        fig_cum.add_hrect(
            y0=sub_stn["cumulative_avg"].min() * 1.1 or -1, y1=0,
            fillcolor=C_DEFICIT, opacity=0.06, layer="below", line_width=0,
        )

        # Peak annotation
        if net_d > 0:
            pi = sub_stn["cumulative_avg"].idxmax()
            ph, pv = sub_stn.loc[pi, "hour"], sub_stn.loc[pi, "cumulative_avg"]
            fig_cum.add_annotation(
                x=ph, y=pv,
                text=f"Peak surplus<br>+{pv:.1f} bikes @ {ph:02d}:00",
                showarrow=True, arrowhead=2,
                font=dict(color=C_SURPLUS, size=11),
                bgcolor="white", bordercolor=C_SURPLUS,
            )
        else:
            pi = sub_stn["cumulative_avg"].idxmin()
            ph, pv = sub_stn.loc[pi, "hour"], sub_stn.loc[pi, "cumulative_avg"]
            fig_cum.add_annotation(
                x=ph, y=pv,
                text=f"Peak deficit<br>{pv:.1f} bikes @ {ph:02d}:00",
                showarrow=True, arrowhead=2,
                font=dict(color=C_DEFICIT, size=11),
                bgcolor="white", bordercolor=C_DEFICIT,
            )

        fig_cum.update_layout(
            title=f"{station_sel2}  ({net_d:+.1f} bikes/day — {season_label})",
            xaxis=dict(title="Hour of day", tickmode="linear", dtick=2),
            yaxis=dict(title="Avg cumulative net flow (bikes)"),
        )
        plotly_layout_defaults(fig_cum, height=380)
        st.plotly_chart(fig_cum, use_container_width=True)

    # Season overlay for selected station
    if season_sel == "All seasons":
        st.markdown(f"#### Seasonal comparison — {station_sel2}")
        fig_sov = go.Figure()
        for s in SEASON_ORDER:
            h_s = compute_hourly(df, valid_stations, n_weekdays, season=s)
            sub_s = h_s[h_s["start_station_name"] == station_sel2]
            if sub_s.empty:
                continue
            fig_sov.add_trace(go.Scatter(
                x=sub_s["hour"], y=sub_s["cumulative_avg"],
                mode="lines+markers",
                name=s,
                line=dict(color=SEASON_COLORS[s], width=2),
                marker=dict(size=4),
            ))
        fig_sov.add_hline(y=0, line_color="black", line_width=1, line_dash="dash")
        fig_sov.update_layout(
            title=f"Cumulative Flow by Season — {station_sel2}",
            xaxis=dict(title="Hour of day", tickmode="linear", dtick=2),
            yaxis=dict(title="Avg cumulative net flow (bikes)"),
        )
        plotly_layout_defaults(fig_sov, height=360)
        st.plotly_chart(fig_sov, use_container_width=True)

    # Small multiples for top 10
    st.markdown("#### Top 10 most imbalanced stations — overview")
    cols_sm = st.columns(5)
    for i, station in enumerate(focus_stations):
        sub = hourly_sel[hourly_sel["start_station_name"] == station]
        if sub.empty:
            continue
        net_d = flow_sel.loc[station, "net_per_day"] if station in flow_sel.index else 0
        color = C_SURPLUS if net_d > 0 else C_DEFICIT
        fig_sm = go.Figure(go.Scatter(
            x=sub["hour"], y=sub["cumulative_avg"],
            mode="lines", line=dict(color=color, width=1.8),
        ))
        fig_sm.add_hline(y=0, line_color="gray", line_width=0.8, line_dash="dot")
        fig_sm.update_layout(
            title=dict(text=f"{station[:22]}<br>({net_d:+.1f}/day)", font=dict(size=10)),
            margin=dict(l=5, r=5, t=40, b=20),
            xaxis=dict(tickmode="linear", dtick=6, tickfont=dict(size=8)),
            yaxis=dict(tickfont=dict(size=8)),
            height=200,
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        cols_sm[i % 5].plotly_chart(fig_sm, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════
# TAB 3 — WEEKDAY vs WEEKEND
# ══════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown(f"### Weekday vs Weekend — {season_label}")

    compare_stations = flow["net_per_day"].abs().nlargest(20).index

    if season_sel == "All seasons":
        df_sub_wd = df[df["is_weekend"] == False]
        df_sub_we = df[df["is_weekend"] == True]
    else:
        df_sub_wd = df[(df["season"] == season_sel) & (df["is_weekend"] == False)]
        df_sub_we = df[(df["season"] == season_sel) & (df["is_weekend"] == True)]

    def _npd(df_s, n):
        if n == 0: return pd.Series(dtype=float)
        dep = df_s.groupby("start_station_name", observed=True).size().rename("dep")
        arr = (df_s[df_s["end_station_name"].isin(valid_stations)]
               .groupby("end_station_name", observed=True).size().rename("arr"))
        f = pd.concat([dep, arr], axis=1).fillna(0)
        return ((f["arr"] - f["dep"]) / n).rename("net_per_day")

    n_wd = df_sub_wd["date"].nunique()
    n_we = max(df_sub_we["date"].nunique(), 1)
    wd_flow = _npd(df_sub_wd, n_wd)
    we_flow = _npd(df_sub_we, n_we)

    compare = pd.DataFrame({
        "Weekday": wd_flow.reindex(compare_stations),
        "Weekend": we_flow.reindex(compare_stations),
    }).fillna(0).round(2)
    compare["flips"] = np.sign(compare["Weekday"]) != np.sign(compare["Weekend"])
    compare = compare.sort_values("Weekday", ascending=False)

    fig_wdwe = go.Figure()
    fig_wdwe.add_trace(go.Bar(
        name="Weekday", x=compare.index, y=compare["Weekday"],
        marker_color=C_SURPLUS, opacity=0.85,
        text=[f"{v:+.1f}" for v in compare["Weekday"]],
        textposition="outside", textfont=dict(size=7),
    ))
    fig_wdwe.add_trace(go.Bar(
        name="Weekend", x=compare.index, y=compare["Weekend"],
        marker_color=C_DEFICIT, opacity=0.85,
        text=[f"{v:+.1f}" for v in compare["Weekend"]],
        textposition="outside", textfont=dict(size=7),
    ))

    # Annotate flips
    for i, (station, row) in enumerate(compare.iterrows()):
        if row["flips"]:
            fig_wdwe.add_annotation(
                x=station, y=max(abs(row["Weekday"]), abs(row["Weekend"])) + 0.3,
                text="↕ flips", showarrow=False,
                font=dict(color="purple", size=9, family="Arial Black"),
            )

    fig_wdwe.update_layout(
        barmode="group",
        title=f"Net Flow — Weekday vs Weekend ({season_label})",
        xaxis_tickangle=-40,
        yaxis_title="Avg net flow per day",
    )
    plotly_layout_defaults(fig_wdwe, height=440)
    st.plotly_chart(fig_wdwe, use_container_width=True)

    flip_stns = compare[compare["flips"]]
    if len(flip_stns) > 0:
        callout(
            f"<strong>{len(flip_stns)} station(s) flip</strong> between surplus and deficit "
            f"on weekdays vs weekends in <strong>{season_label}</strong>: "
            + ", ".join(flip_stns.index.tolist())
        )


# ══════════════════════════════════════════════════════════════════════
# TAB 4 — SEGMENTS (bike type + rider type)
# ══════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown(f"### Net Flow by Segment — {season_label}")
    top15 = flow_sel["net_per_day"].abs().nlargest(15).index

    seg_tab1, seg_tab2 = st.tabs(["🚴 Bike Type", "👤 Rider Type"])

    with seg_tab1:
        seg_bike = {}
        for bike in ["electric_bike", "classic_bike"]:
            sub = df[df["rideable_type"] == bike]
            if season_sel != "All seasons":
                sub = sub[sub["season"] == season_sel]
            n = sub["date"].nunique()
            if n == 0: continue
            dep = sub.groupby("start_station_name", observed=True).size().rename("dep")
            arr = (sub[sub["end_station_name"].isin(valid_stations)]
                   .groupby("end_station_name", observed=True).size().rename("arr"))
            f = pd.concat([dep, arr], axis=1).fillna(0)
            seg_bike[bike] = ((f["arr"] - f["dep"]) / n).reindex(top15).fillna(0)

        if seg_bike:
            bike_df = pd.DataFrame(seg_bike).fillna(0)
            fig_bike = go.Figure()
            for bike, color in [("electric_bike", C_SURPLUS), ("classic_bike", C_DEFICIT)]:
                if bike not in bike_df.columns: continue
                fig_bike.add_trace(go.Bar(
                    name=bike.replace("_", " ").title(),
                    x=bike_df.index, y=bike_df[bike],
                    marker_color=color, opacity=0.85,
                    text=[f"{v:+.1f}" for v in bike_df[bike]],
                    textposition="outside", textfont=dict(size=7),
                ))
            fig_bike.update_layout(
                barmode="group",
                title=f"Net Flow by Bike Type — {season_label}",
                xaxis_tickangle=-40,
                yaxis_title="Avg net flow per day",
            )
            plotly_layout_defaults(fig_bike, height=420)
            st.plotly_chart(fig_bike, use_container_width=True)
            callout(
                "If electric and classic bars point in the same direction, both bike types "
                "drive the same imbalance. If they diverge, the rebalancing need is "
                "bike-type-specific — the truck needs to move the right type, not just any bike."
            )

    with seg_tab2:
        seg_user = {}
        for user in ["member", "casual"]:
            sub = df[df["member_casual"] == user]
            if season_sel != "All seasons":
                sub = sub[sub["season"] == season_sel]
            n = sub["date"].nunique()
            if n == 0: continue
            dep = sub.groupby("start_station_name", observed=True).size().rename("dep")
            arr = (sub[sub["end_station_name"].isin(valid_stations)]
                   .groupby("end_station_name", observed=True).size().rename("arr"))
            f = pd.concat([dep, arr], axis=1).fillna(0)
            seg_user[user] = ((f["arr"] - f["dep"]) / n).reindex(top15).fillna(0)

        if seg_user:
            user_df = pd.DataFrame(seg_user).fillna(0)
            fig_user = go.Figure()
            for user, color in [("member", COLORS["member"]), ("casual", COLORS["casual"])]:
                if user not in user_df.columns: continue
                fig_user.add_trace(go.Bar(
                    name=user.title(),
                    x=user_df.index, y=user_df[user],
                    marker_color=color, opacity=0.85,
                    text=[f"{v:+.1f}" for v in user_df[user]],
                    textposition="outside", textfont=dict(size=7),
                ))
            fig_user.update_layout(
                barmode="group",
                title=f"Net Flow by Rider Type — {season_label}",
                xaxis_tickangle=-40,
                yaxis_title="Avg net flow per day",
            )
            plotly_layout_defaults(fig_user, height=420)
            st.plotly_chart(fig_user, use_container_width=True)
            callout(
                "Member-driven imbalance is predictable and schedulable — members commute at the "
                "same times every weekday. Casual-driven imbalance is weather-sensitive and "
                "requires more reactive response."
            )


# ══════════════════════════════════════════════════════════════════════
# TAB 5 — PRIORITY SCHEDULE
# ══════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown(f"### Priority Schedule — {season_label}")
    st.caption(
        "Stations ranked by severity. "
        "⚠ action_by = hour at which imbalance peaks — intervene before this time."
    )

    col_p, col_d = st.columns(2)

    with col_p:
        st.markdown(f"#### 🔴 Pickup stations  (surplus — remove bikes)")
        sub_p = pickup_sched.head(15).sort_values("severity")
        fig_p = go.Figure(go.Bar(
            x=sub_p["severity"], y=sub_p["station"],
            orientation="h",
            marker_color=C_SURPLUS, marker_line_width=0,
            text=[f"⚠ by {r.action_by} ({r.net_per_day:+.1f}/day)"
                  for r in sub_p.itertuples()],
            textposition="outside", textfont=dict(size=8),
            hovertemplate="<b>%{y}</b><br>Severity: %{x:.1f} bikes<extra></extra>",
        ))
        fig_p.update_layout(title="Top 15 Pickup Stations")
        plotly_layout_defaults(fig_p, height=460)
        col_p.plotly_chart(fig_p, use_container_width=True)

    with col_d:
        st.markdown(f"#### 🔵 Delivery stations  (deficit — deliver bikes)")
        sub_d = delivery_sched.head(15).sort_values("severity")
        fig_d = go.Figure(go.Bar(
            x=sub_d["severity"], y=sub_d["station"],
            orientation="h",
            marker_color=C_DEFICIT, marker_line_width=0,
            text=[f"⚠ by {r.action_by} ({r.net_per_day:+.1f}/day)"
                  for r in sub_d.itertuples()],
            textposition="outside", textfont=dict(size=8),
            hovertemplate="<b>%{y}</b><br>Severity: %{x:.1f} bikes<extra></extra>",
        ))
        fig_d.update_layout(title="Top 15 Delivery Stations")
        plotly_layout_defaults(fig_d, height=460)
        col_d.plotly_chart(fig_d, use_container_width=True)

    # Seasonal severity comparison
    if season_sel == "All seasons":
        st.markdown("#### Severity by Season — Top 15 Stations")
        top_stns = schedule["station"].head(15).tolist()
        sev_data = {}
        for s in SEASON_ORDER:
            fs = compute_season_flow(df, valid_stations, flow, s)
            hs = compute_hourly(df, valid_stations, n_weekdays, season=s)
            if fs is None or hs.empty: continue
            sched_s = build_schedule(hs, fs)
            sev_data[s] = sched_s.set_index("station")["severity"].reindex(top_stns).fillna(0)

        if sev_data:
            sev_df = pd.DataFrame(sev_data)
            fig_sev = go.Figure()
            for s in SEASON_ORDER:
                if s not in sev_df.columns: continue
                fig_sev.add_trace(go.Bar(
                    name=s, x=sev_df.index, y=sev_df[s],
                    marker_color=SEASON_COLORS[s], opacity=0.85,
                ))
            fig_sev.update_layout(
                barmode="group",
                title="Rebalancing Severity by Season",
                xaxis_tickangle=-40,
                yaxis_title="Peak severity (bikes)",
            )
            plotly_layout_defaults(fig_sev, height=400)
            st.plotly_chart(fig_sev, use_container_width=True)

    # Downloadable schedule
    st.markdown("#### Full schedule table")
    st.dataframe(
        schedule[["station","role","net_per_day","severity","action_by","imbalance_pct"]]
        .rename(columns={
            "net_per_day":   "net/day",
            "imbalance_pct": "imbal%",
        }),
        use_container_width=True,
        height=320,
    )
    csv_bytes = schedule.to_csv(index=False).encode()
    st.download_button(
        "⬇ Download schedule CSV",
        data=csv_bytes,
        file_name=f"rebalancing_schedule_{season_label.lower().replace(' ','_')}.csv",
        mime="text/csv",
    )


# ══════════════════════════════════════════════════════════════════════
# TAB 6 — PAIRING MAP
# ══════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown(f"### Pickup → Delivery Pairing Map — {season_label}")
    st.caption(
        "Optimal assignment using the Hungarian algorithm — minimises total truck distance. "
        "Each pickup station is assigned to at most one delivery station. "
        "Arrow = recommended truck route. Size = total trips."
    )

    pickups_df    = schedule[(schedule["role"] == "pickup")   & schedule["lat"].notna()].head(20)
    deliveries_df = schedule[(schedule["role"] == "delivery") & schedule["lat"].notna()].head(20)

    if len(pickups_df) > 0 and len(deliveries_df) > 0:
        dist_matrix = cdist(
            pickups_df[["lat","lng"]].values,
            deliveries_df[["lat","lng"]].values,
        ) * 111  # degrees → km

        dist_df = pd.DataFrame(
            dist_matrix,
            index=pickups_df["station"],
            columns=deliveries_df["station"],
        ).round(2)

        # ── Hungarian algorithm ───────────────────────────────────────
        # Pad to square so linear_sum_assignment can handle unequal counts
        n_p, n_d = dist_matrix.shape
        size = max(n_p, n_d)
        padded = np.full((size, size), fill_value=dist_matrix.max() * 10)
        padded[:n_p, :n_d] = dist_matrix

        row_ind, col_ind = linear_sum_assignment(padded)

        pickup_stations   = pickups_df["station"].tolist()
        delivery_stations = deliveries_df["station"].tolist()
        pickup_meta       = pickups_df.set_index("station")
        delivery_meta     = deliveries_df.set_index("station")

        pairings = []
        for r, c in zip(row_ind, col_ind):
            if r >= n_p or c >= n_d:
                continue  # padded cell — no real station
            p_stn = pickup_stations[r]
            d_stn = delivery_stations[c]
            pairings.append({
                "pickup":   p_stn,
                "delivery": d_stn,
                "dist_km":  round(dist_matrix[r, c], 2),
                "surplus":  round(float(pickup_meta.loc[p_stn,   "net_per_day"]), 2),
                "deficit":  round(float(delivery_meta.loc[d_stn, "net_per_day"]), 2),
            })

        pairings_df = pd.DataFrame(pairings).sort_values("deficit").reset_index(drop=True)
        # ── End Hungarian ─────────────────────────────────────────────

        # Build scatter map with plotly
        fig_map = go.Figure()

        # All stations bubble
        vmax = flow_sel["net_per_day"].abs().max()
        fig_map.add_trace(go.Scatter(
            x=flow_sel["lng"], y=flow_sel["lat"],
            mode="markers",
            marker=dict(
                size=np.sqrt(flow_sel["total_trips"] / flow_sel["total_trips"].max()) * 30 + 4,
                color=flow_sel["net_per_day"],
                colorscale=[[0, C_DEFICIT], [0.5, "#EEEEEE"], [1, C_SURPLUS]],
                cmin=-vmax, cmax=vmax,
                colorbar=dict(title="Net/day", thickness=12),
                opacity=0.45,
                line_width=0,
            ),
            hovertext=flow_sel.index + "<br>" + flow_sel["net_per_day"].apply(lambda v: f"{v:+.2f}/day"),
            hoverinfo="text",
            name="All stations",
            showlegend=False,
        ))

        # Pickup markers
        fig_map.add_trace(go.Scatter(
            x=pickups_df["lng"], y=pickups_df["lat"],
            mode="markers+text",
            marker=dict(symbol="triangle-up", size=14, color=C_SURPLUS, line_width=1, line_color="white"),
            text=pickups_df["station"].str[:18],
            textposition="top right",
            textfont=dict(size=8, color=C_SURPLUS),
            name="Pickup (surplus)",
            hovertext=pickups_df["station"] + "<br>" + pickups_df["net_per_day"].apply(lambda v: f"{v:+.2f}/day"),
            hoverinfo="text",
        ))

        # Delivery markers
        fig_map.add_trace(go.Scatter(
            x=deliveries_df["lng"], y=deliveries_df["lat"],
            mode="markers+text",
            marker=dict(symbol="triangle-down", size=14, color=C_DEFICIT, line_width=1, line_color="white"),
            text=deliveries_df["station"].str[:18],
            textposition="bottom right",
            textfont=dict(size=8, color=C_DEFICIT),
            name="Delivery (deficit)",
            hovertext=deliveries_df["station"] + "<br>" + deliveries_df["net_per_day"].apply(lambda v: f"{v:+.2f}/day"),
            hoverinfo="text",
        ))

        # Pairing arrows as shapes
        shapes = []
        annotations = []
        for _, row in pairings_df.iterrows():
            p_row = pickups_df[pickups_df["station"] == row["pickup"]]
            d_row = deliveries_df[deliveries_df["station"] == row["delivery"]]
            if p_row.empty or d_row.empty:
                continue
            p_lng, p_lat = float(p_row["lng"].iloc[0]), float(p_row["lat"].iloc[0])
            d_lng, d_lat = float(d_row["lng"].iloc[0]), float(d_row["lat"].iloc[0])
            shapes.append(dict(
                type="line",
                x0=p_lng, y0=p_lat, x1=d_lng, y1=d_lat,
                line=dict(color="black", width=1.2, dash="solid"),
                xref="x", yref="y",
            ))
            annotations.append(dict(
                x=(p_lng + d_lng) / 2, y=(p_lat + d_lat) / 2,
                text=f"{row['dist_km']:.1f}km",
                showarrow=False,
                font=dict(size=7, color="#333"),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=2,
            ))

        fig_map.update_layout(
            shapes=shapes,
            annotations=annotations,
            title=f"Pairing Map — {season_label}  (Hungarian algorithm)",
            xaxis=dict(title="Longitude", gridcolor="#EEE"),
            yaxis=dict(title="Latitude",  gridcolor="#EEE", scaleanchor="x", scaleratio=1.2),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        )
        plotly_layout_defaults(fig_map, height=620)
        st.plotly_chart(fig_map, use_container_width=True)

        # Pairings table
        st.markdown("#### Recommended pairings")
        st.dataframe(
            pairings_df.rename(columns={
                "pickup":   "Pickup station",
                "delivery": "Delivery station",
                "dist_km":  "Distance (km)",
                "surplus":  "Pickup net/day",
                "deficit":  "Delivery net/day",
            }),
            use_container_width=True,
        )

        total_dist = pairings_df["dist_km"].sum()
        callout(
            f"Assignments use the <strong>Hungarian algorithm</strong> — each pickup station "
            f"is used at most once, minimising total truck distance across all pairs. "
            f"Total assigned distance: <strong>{total_dist:.1f} km</strong>."
        )
    else:
        st.info("Insufficient coordinate data to build the pairing map — check lat/lng columns.")