# Citi Bike — Jersey City & Hoboken Analysis (Dec 2024 – Jan 2026)

End-to-end data analysis of **1,093,685 Citi Bike trips** across the Jersey City and Hoboken service area, covering 14 months of data and delivered through a 7-page interactive Streamlit dashboard.

---

## Key Numbers

| Metric | Value |
|---|---|
| Total trips (clean) | 1,093,685 |
| Date range | Dec 2024 – Jan 2026 |
| Member share | 78.4% |
| Electric bike share | 64.6% |
| Unique start stations | 112 |
| Months covered | 14 |
| Peak month | Sep 2025 — 115,706 trips |
| Winter floor | Feb 2025 — 45,152 trips |

---

## Project Structure

```
citibike-project/
├── data/
│   ├── zips/                          # downloaded .zip files (gitignored)
│   ├── csv/                           # extracted monthly CSVs (gitignored)
│   ├── jc_trips_clean.csv             # cleaned dataset — 1,093,685 rows, 238.6 MB
│   └── daily_weather_merged.csv       # daily trip counts merged with NOAA weather
├── notebooks/
│   ├── 01_data_collection.ipynb       # download & extract from S3
│   ├── 02_data_cleaning.ipynb         # full cleaning pipeline
│   └── 03_eda.ipynb                   # feature engineering + all EDA sections
├── streamlit_app/
│   ├── app.py                         # entry point
│   ├── utils.py                       # cached data loader, design tokens, shared helpers
│   └── pages/
│       ├── 1_Overview.py              # KPIs, monthly trend, MoM change, casual share
│       ├── 2_Temporal.py              # heatmap, hourly profiles, seasonal, DoW
│       ├── 3_Member_vs_Casual.py      # duration, distance, speed, behaviour grid, stats
│       ├── 4_Stations.py              # top stations, net flow, explorer, network analysis
│       ├── 5_Map.py                   # pydeck hexbin + station bubble map
│       ├── 6_Rideable_Type.py         # electric vs classic deep dive
│       └── 7_Weather.py               # temperature, rain, snow impact on ridership
├── figures/                           # exported EDA plots (.png)
├── requirements.txt
└── README.md
```

---

## Setup & Reproduction

```bash
git clone <repo-url>
cd citibike-project

conda create -n citibike_venv python=3.11
conda activate citibike_venv
pip install -r requirements.txt
```

Run notebooks in order:

```bash
jupyter notebook notebooks/01_data_collection.ipynb   # downloads 14 monthly zip files
jupyter notebook notebooks/02_data_cleaning.ipynb     # outputs jc_trips_clean.csv
jupyter notebook notebooks/03_eda.ipynb               # outputs figures/ and daily_weather_merged.csv
```

Launch the dashboard:

```bash
cd streamlit_app
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Data Source

Monthly trip files downloaded programmatically from the official Citi Bike S3 bucket:

```
https://s3.amazonaws.com/tripdata/
```

Two filename conventions are handled automatically:

```
JC-YYYYMM-citibike-tripdata.csv.zip   # older format
JC-YYYYMM-citibike-tripdata.zip        # newer format
```

Weather data: NOAA NCEI Daily Summaries API, LaGuardia Airport station (`USW00014732`), metric units.

---

## What Was Done

### 1. Data Acquisition
Downloaded 14 monthly JC trip files (Dec 2024 – Jan 2026) and extracted them into `data/csv/`. A `source_month` column was added to each row via regex extraction of the `YYYYMM` pattern from the filename, making the pipeline robust to naming convention changes.

Raw row count: **1,097,581 trips** across 13 columns.

### 2. Data Cleaning (`02_data_cleaning.ipynb`)

A multi-stage pipeline with a `snapshot()` helper reporting row counts and missing value percentages at each stage:

| Stage | Action | Rows removed |
|---|---|---|
| Dtype optimisation | Parse datetimes, cast categoricals, downcast float64 → float32 | 0 |
| Deduplication | Check exact duplicates and duplicate `ride_id` | 0 |
| Duration filter | Remove trips < 60 s or > 24 h | 482 |
| Coordinate validation | Null out-of-bounds end coords (JC/HB bounding box) | 7 nulled |
| Station standardisation | Strip/collapse whitespace, audit name→ID mapping | 0 |
| Categorical audit | Confirm no unexpected values in `rideable_type` / `member_casual` | 0 |
| Critical field filter | Drop rows missing ride_id, timestamps, station names, user type | 3,414 |

**Output:** `jc_trips_clean.csv` — 1,093,685 rows, 18 columns, 238.6 MB (427.5 MB in memory).

Remaining missing values are structurally expected: `end_station_id` (0.14%) and end coordinates (0.12%) represent dockless electric bike trips that ended without docking.

### 3. Feature Engineering (`03_eda.ipynb`)

**Temporal:** `hour`, `day_of_week`, `day_name`, `month`, `date`, `is_weekend`, `is_rush` (AM 7–9, PM 17–19), `season`

**Geospatial:** `distance_m` and `distance_km` (Haversine formula), `speed_kmh` (filtered to distance > 50 m, duration > 1 min)

**Network / classification:** `start_network` / `end_network` (jersey_city | hoboken | other), `is_cross_hudson`, `trip_type` (JC→JC, HB→HB, JC→HB, HB→JC, Other)

### 4. Exploratory Data Analysis (`03_eda.ipynb`)

All 12 EDA figures saved to `figures/`:

| Figure | Description |
|---|---|
| `01_monthly_ridership` | Monthly volume stacked by local / cross-Hudson + MoM % change |
| `02_monthly_member_casual` | Monthly member vs casual stacked bar + casual share % line |
| `03_heatmap_dow_hour` | Day-of-week × hour demand heatmap |
| `04_hourly_weekday_weekend` | Hourly profiles split weekday/weekend with rush-hour bands |
| `05_duration_distribution` | Duration histogram overlay + box plot by user × bike type |
| `06_distance_distribution` | Distance histogram + distance vs duration scatter (5k sample) |
| `07_speed_analysis` | Speed violin by user × bike type + median speed by hour |
| `08_member_casual_behaviour` | 4-panel behavioural profile: bike type, weekend, rush, season |
| `09_top_start_stations` | Top 20 start stations with casual % annotation |
| `10_station_net_flow` | Top 20 most imbalanced stations (departures − arrivals) |
| `11_rideable_type_analysis` | Electric share by month, hourly by bike type, duration by bike type |
| `12_network_analysis` | Trip type pie + cross-network (JC↔HB) hourly flow lines |
| `bimodal_01_kde_peaks` | KDE with detected peaks for casual and member distance distributions |
| `bimodal_02_gmm_components` | GMM fit (1–3 components, BIC selection) for each user type |
| `bimodal_03_casual_profiles` | Two GMM-split casual populations: distance, hourly demand, weekend share |

The casual distance distribution is weakly bimodal statistically (GMM BIC improves from 514k to 457k with 2 components) but the two sub-populations show negligible behavioural differences — same bike preference, weekend share, and rush-hour share. The member/casual split remains the more structurally meaningful segmentation.

Station net flow analysis identifies **Grove St PATH** as the single most imbalanced station (+3,108 net arrivals overall), followed by both Hoboken Terminal entrances. Residential neighbourhood stations are the mirror: chronic net exporters. This commuter-drain pattern provides the empirical foundation for the rebalancing analysis in `04_rebalancing.ipynb`.

### 5. Weather Integration (`03_eda.ipynb`)

Daily weather data fetched from NOAA NCEI (427 days, Dec 2024 – Jan 2026): `TMAX`, `TMIN`, `TAVG`, `PRCP`, `SNOW`, `AWND`.

Engineered features: `temp_avg` (imputed where TAVG missing), `is_rain` (precipitation > 1 mm), `is_snow`, `temp_category` (Freezing / Cold / Mild / Warm), `wind_speed`.

Trip data aggregated to daily level (wide format: one row per date) and left-joined on `date`. Output: `data/daily_weather_merged.csv`.

### 6. Rebalancing Analysis (`04_rebalancing.ipynb`)

Builds on the station net flow findings to produce an operational rebalancing plan. All outputs go to `figures/reb_*.png` and `data/rebalancing_*.csv`.

| Figure | Description |
|---|---|
| `reb_01b_bike_type_flow` | Net flow per day split by electric vs classic — top 15 stations |
| `reb_01b_rider_type_flow` | Net flow per day split by member vs casual — top 15 stations |
| `reb_01b_season_flow` | Net flow per day by season — top 15 stations |
| `reb_01b_hourly_by_rider_type` | Cumulative net flow by rider type at the worst station |
| `reb_02_cumulative_flow_top10` | Hourly cumulative net flow (average weekday) — top 10 stations |
| `reb_02b_cumulative_flow_by_season` | Same, with all 4 seasons overlaid per panel |
| `reb_02c_worst_station_by_season` | Full seasonal detail with annotations for the single worst station |
| `reb_03_heatmap_overall` | Station × hour risk heatmap — average weekday, all seasons |
| `reb_03b_heatmap_by_season` | Same heatmap, one panel per season |
| `reb_03c_heatmap_summer_minus_winter` | Seasonal delta heatmap: Summer − Winter |
| `reb_04_weekday_vs_weekend_overall` | Net flow per day: weekday vs weekend, all seasons combined |
| `reb_04b_weekday_vs_weekend_by_season` | Same comparison, one panel per season |
| `reb_04c_weekday_by_season` | Weekday net flow across all 4 seasons — top 20 stations |
| `reb_05_weather_overall` | Daily net flow vs temperature at worst surplus/deficit station |
| `reb_05b_weather_by_season_scatter` | Same scatter, coloured by season with per-season trend lines |
| `reb_05c_rain_impact_by_season` | Rain impact box plots by season for surplus and deficit station |
| `reb_05d_temp_category_by_season` | Avg net flow by season × temperature category (Freezing/Cold/Mild/Warm) |
| `reb_06_priority_schedule_overall` | Priority schedule bar chart — all seasons combined |
| `reb_06_{season}_priority_schedule` | Per-season priority schedules (4 charts) |
| `reb_06_severity_by_season_comparison` | Peak severity by season — top 15 stations |
| `reb_06_action_hour_by_season` | When to intervene: action hour per station by season |
| `reb_07_pairing_map_overall` | Pickup → delivery route map with distances — all seasons |
| `reb_07_{season}_pairing_map` | Per-season pairing maps (4 charts) |
| `reb_07_pairing_distance_by_season` | Truck distance per pairing by season |

**Priority schedule** (`data/rebalancing_priority_schedule_*.csv`) — one file overall and one per season. Each row gives a station its `role` (pickup or delivery), `severity` (peak average cumulative imbalance in bikes), and `action_by` (the hour at which the imbalance peaks and intervention is most urgent).

**Donor/recipient pairing** uses the Hungarian algorithm (globally optimal minimum-distance assignment) to match surplus stations to deficit stations. A stability table checks whether the same pairs hold across seasons; a distance comparison chart shows whether the truck travels further in some seasons due to shifting imbalance patterns.

**Summary CSV** (`data/rebalancing_summary_by_season.csv`) — cross-season comparison of surplus/deficit station counts, worst station per role, earliest intervention times, and total system-level imbalance in bikes per day.

### 7. Streamlit Dashboard (`streamlit_app/`)

8-page interactive dashboard built with Plotly + pydeck, styled in Citi Bike brand colours (`#0055A5` / `#00AEEF`). All data loaded once via `@st.cache_data` — subsequent interactions operate on the cached 1.09 M-row dataframe.

| Page | Contents |
|---|---|
| **1 · Overview** | KPI cards, monthly ridership (local vs cross-Hudson), MoM % change, casual share trend line, bike type breakdown, summary stats table |
| **2 · Temporal** | Day × hour demand heatmap, weekday/weekend hourly profiles with rush-hour bands, seasonal grouped bars, day-of-week breakdown |
| **3 · Member vs Casual** | Duration (histogram + box), distance (histogram + scatter), speed (violin + hourly median), 4-panel behaviour grid, Mann-Whitney U test |
| **4 · Stations** | Top-N bar (coloured by casual %), net flow imbalance chart, per-station explorer (hourly profile + top 10 destinations + monthly trend), network & trip-type analysis |
| **5 · Map** | Extruded 3D hexbin (HexagonLayer) for trip origin density; station bubble map (ScatterplotLayer) sized by volume and coloured by casual share |
| **6 · Rideable Type** | Monthly electric share trend, hourly usage by bike type, duration distribution by bike type, electric preference by user type and season |
| **7 · Weather** | Daily trip trend with 7-day rolling average, temperature scatter + OLS trendline, avg trips by temp category, rain/snow impact bars, member vs casual rain box plots, wind speed scatter |

---

## Key Findings

**Seasonality** is the dominant driver of ridership volume — a ~3:1 peak-to-trough ratio between Sep 2025 and Feb 2025. The network handles ~75k–115k trips/month at peak and ~40k–50k in winter.

**Members (78.4%)** ride shorter, faster and more predictably than casual riders — consistent with commuter use. They show strong bimodal weekday peaks (AM/PM rush) and relatively flat weekend curves.

**Casual riders (21.6%)** take ~1.8× longer trips (median ~6 min longer), concentrate usage on weekends and summer, and show a much stronger seasonal swing. The duration difference is statistically significant (Mann-Whitney U, p < 0.0001).

**Electric bikes** are preferred by both user types but more strongly by casual riders (~68% vs ~63%). Electric bikes show measurably higher median speeds.

**Station net flow** reveals chronic imbalances at transit hub stations (near PATH stations and ferry terminals), which drain in the AM and refill in the PM — a clear operational rebalancing signal.

**Cross-Hudson trips** (~3,571, 0.33% of dataset) represent one-way commuters who start in JC/Hoboken and dock in NYC, explaining why 387 NYC station names appear only as end stations.

---

## Tech Stack

| Layer | Tools |
|---|---|
| Language | Python 3.11 (conda: `citibike_venv`) |
| Data | pandas 2.x, numpy |
| Statistics | scipy (Mann-Whitney U) |
| EDA visualisation | matplotlib, seaborn |
| Dashboard charts | Plotly |
| Geospatial | pydeck (deck.gl), Haversine formula |
| Weather | NOAA NCEI Daily Summaries API |
| Dashboard | Streamlit ≥ 1.32 |

### Key dependencies

```
pandas>=2.0.0
numpy<2.0.0
matplotlib>=3.7.0
seaborn>=0.12.0
scipy>=1.12.0
plotly>=5.20.0
pydeck>=0.8.0
streamlit>=1.32.0
pyarrow>=15.0.0
requests
```

---

## Possible Extensions

- Merge with PATH train ridership data to test correlation between transit disruptions and bike share spikes
- Predictive model: forecast next-day ridership from weather forecast
- Station clustering: group the 112 stations by hourly demand profile using k-means
- Live dashboard mode using the real-time Citi Bike station availability API
- Streamlit Community Cloud deployment for public portfolio sharing
