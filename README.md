# Citi Bike Jersey City Analysis (2024–2026)

Exploratory analysis of Citi Bike trip data focused on **Jersey City (JC)** stations, covering the most recent 14 months of available data (approximately December 2024 – January 2026).

Goal: Understand usage patterns, user behavior (member vs casual), temporal trends, spatial distribution, and prepare the dataset for merging with weather data (next step).

## Project Structure

citibike-project/
├── data/
│   ├── zips/                     # downloaded .zip files (not in git)
│   ├── csv/                      # extracted monthly CSV files (not in git)
│   └── jc_trips_combined_*.csv   # merged & cleaned dataset
├── notebooks/
│   ├── 01_data_collection.ipynb   # download & extract JC files
│   └── 02_datacleaning.ipynb  # loading, cleaning
│   └── 03_eda.ipynb  # loading, cleaning
├── requirements.txt              # Python dependencies (pip freeze)
└── README.md


## What Has Been Done (So far)

1. **Data Acquisition**
   - Downloaded Jersey City (JC) Citi Bike monthly trip files from official S3 bucket:  
     `https://s3.amazonaws.com/tripdata/`
   - Focused on the most recent 14 months available (latest file at time of analysis: JC-202601)
   - Handled both filename variants:  
     - `JC-YYYYMM-citibike-tripdata.csv.zip`  
     - `JC-YYYYMM-citibike-tripdata.zip`
   - Extracted CSVs into `data/csv/`

2. **Data Preparation**
   - Concatenated all monthly JC files into one dataset
   - Saved merged file: `jc_trips_combined_202412_202601.csv` (~1.1 million trips)
   - Parsed `started_at` and `ended_at` as datetime (with microsecond support)
   - Calculated `duration_sec` and `duration_min`
   - Removed 7 invalid records (negative duration)

3. **Dataset Summary (as of March 2026)**
   - Total trips: **1,097,581**
   - Date range: Nov 30, 2024 – Jan 31, 2026
   - Rideable types: electric_bike (~65%), classic_bike (~35%)
   - User types: member (~78%), casual (~22%)
   - Missing values: very low (<0.5% on end station fields)

4. **Exploratory Data Analysis (EDA) – Initial**
   - Temporal patterns: daily, monthly, hourly (weekday vs weekend)
   - Duration distribution: member vs casual (casual rides significantly longer)
   - Top start/end stations
   - Basic geospatial preparation (lat/lng columns ready)

5. **Visualization Attempts**
   - Matplotlib + Seaborn: time series, histograms, bar plots, heatmaps
   - Interactive geospatial: tried kepler.gl (didn't work in environment) → switched to **lonboard**

6. **Environment**
   - Python 3.10+ (conda environment: `citibike` / `citibike_venv`)
   - Dependencies captured via:
     ```bash
     pip freeze > requirements.txt

7. **Next Steps (Planned)**
- Finish geospatial visualization with lonboard (trip paths, heatmaps, member vs casual overlays)
- Merge with NOAA weather data (LaGuardia station) by date
- Analyze weather impact on ridership (rain, temperature, wind)
- Feature engineering: ride distance, time-of-day flags, season, etc.
- Statistical summaries / hypothesis testing (member vs casual behavior)
- Streamlit dashboard

8. **How to Reproduce**
- Clone the repo
- Create conda environment
```bash
   conda create -n citibike python=3.11
    conda activate citibike
    pip install -r requirements.txt
```

