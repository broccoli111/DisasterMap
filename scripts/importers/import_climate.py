"""
Climate extremes importer for heatwaves, cold waves, and droughts.
Sources: NOAA Climate Extremes Index, ERA5 reanalysis data.
Since full ERA5 requires Copernicus API key, this importer:
1. Reads any pre-downloaded climate data
2. Can generate events from NOAA summaries
3. Falls back to curated event lists
"""

import os
import sys
import glob
import json
import math
import random

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.normalize import *
from scripts.utils.geo import *


def _clamp_lat(lat):
    if lat is None:
        return None
    return max(-90.0, min(90.0, float(lat)))


def _clamp_lon(lon):
    if lon is None:
        return None
    return max(-180.0, min(180.0, float(lon)))

RAW_DIR = 'raw/climate'

KNOWN_HEATWAVES = [
    (1980, '1980 US Heat Wave', 'United States', 'Central/Eastern US', 4, 10000, 'Severe heat wave and drought across the central and eastern US', -90.0, 38.0, 800),
    (1988, '1988 North American Drought & Heat', 'United States', 'Central US', 4, 5000, 'Widespread drought and heat across the US and Canada', -95.0, 40.0, 900),
    (1995, '1995 Chicago Heat Wave', 'United States', 'Midwest', 4, 739, 'Devastating heat wave centered on Chicago in July', -87.6, 41.9, 200),
    (1998, '1998 India Heat Wave', 'India', 'Northern India', 5, 2541, 'Extreme temperatures exceeding 50C in parts of India', 78.0, 26.0, 600),
    (2003, '2003 European Heat Wave', 'France', 'Western Europe', 5, 70000, 'Record-breaking heat wave across Europe, devastating France, Italy, Spain', 2.3, 46.0, 1000),
    (2006, '2006 European Heat Wave', 'France', 'Western Europe', 3, 2065, 'Severe summer heat across Western Europe', 2.3, 46.0, 800),
    (2006, '2006 North American Heat Wave', 'United States', 'Western US', 4, 225, 'Extreme heat across western North America July-August', -115.0, 36.0, 700),
    (2007, '2007 Greek Heat Wave', 'Greece', 'Southeast Europe', 4, 1100, 'Record temperatures up to 46C accompanied by wildfires', 23.7, 38.0, 400),
    (2010, '2010 Russian Heat Wave', 'Russia', 'Western Russia', 5, 55000, 'Record-breaking heat wave in Russia with massive wildfires and crop failure', 40.0, 55.0, 1200),
    (2010, '2010 Pakistan Heat Wave', 'Pakistan', 'Southern Pakistan', 4, 1700, 'Extreme temperatures exceeding 53.5C at Mohenjo-daro', 68.0, 27.0, 500),
    (2012, '2012 North American Heat Wave', 'United States', 'Central/Eastern US', 4, 82, 'Widespread extreme heat and drought across the US', -90.0, 38.0, 900),
    (2013, '2013 Australian Heat Wave', 'Australia', 'Eastern Australia', 4, 374, 'Record-breaking summer heat leading to bush fires', 148.0, -30.0, 800),
    (2015, '2015 Indian Heat Wave', 'India', 'Southern/Eastern India', 5, 2500, 'Severe heat wave in Andhra Pradesh and Telangana', 79.0, 17.0, 500),
    (2015, '2015 Pakistan Heat Wave', 'Pakistan', 'Sindh/Karachi', 5, 2000, 'Extreme heat wave centered on Karachi during Ramadan', 67.0, 25.0, 300),
    (2016, '2016 India Heat Wave', 'India', 'Rajasthan/Maharashtra', 4, 1111, 'Extreme temperatures reaching 51C in Rajasthan', 73.0, 26.0, 600),
    (2017, '2017 Lucifer Heat Wave', 'Italy', 'Southern Europe', 3, 200, 'Extreme heat wave "Lucifer" across Mediterranean Europe', 13.0, 41.0, 700),
    (2018, '2018 Global Heat Wave', 'Japan', 'Northern Hemisphere', 4, 1032, 'Simultaneous heat waves across Japan, Europe, North America', 139.0, 36.0, 500),
    (2018, '2018 European Heat Wave', 'United Kingdom', 'Northern Europe', 3, 863, 'Prolonged heat and drought across Scandinavia and UK', 0.0, 54.0, 800),
    (2019, '2019 European Heat Wave', 'France', 'Western Europe', 4, 1462, 'New all-time records set: 46C in France, 42.6C in Germany', 2.3, 46.0, 800),
    (2019, '2019 India Heat Wave', 'India', 'Northern India', 4, 184, 'Prolonged heat with temperatures above 50C', 77.0, 28.0, 500),
    (2020, '2020 Siberia Heat Wave', 'Russia', 'Siberia', 5, 0, 'Record 38C in Verkhoyansk, unprecedented Arctic heat', 133.4, 67.5, 1000),
    (2021, '2021 Pacific Northwest Heat Dome', 'United States', 'Pacific Northwest', 5, 1400, 'Record-shattering heat dome: 49.6C in Lytton, BC', -122.0, 48.0, 600),
    (2022, '2022 European Heat Wave', 'United Kingdom', 'Western Europe', 4, 61000, 'Record 40.3C in UK, widespread fires and heat deaths', -1.0, 51.0, 900),
    (2022, '2022 China Heat Wave', 'China', 'Yangtze River Valley', 5, 0, 'Longest and most intense heat wave in Chinese records', 110.0, 30.0, 1000),
    (2022, '2022 India-Pakistan Heat Wave', 'India', 'South Asia', 4, 90, 'Record March-May heat affecting 1 billion people', 73.0, 28.0, 800),
    (2023, '2023 Southern Europe Heat Wave', 'Italy', 'Mediterranean', 4, 3500, 'Heat wave Cerberus/Charon: 48.2C in Sardinia', 12.0, 40.0, 700),
    (2023, '2023 US Southwest Heat', 'United States', 'Southwest', 4, 645, 'Phoenix hit 31 consecutive days above 43C', -112.0, 33.4, 500),
    (2023, '2023 China Heat Wave', 'China', 'Northwest China', 4, 0, 'Record 52.2C in Xinjiang, widespread extreme heat', 87.0, 42.0, 700),
    (2024, '2024 Sahel Heat Wave', 'Mali', 'West Africa', 5, 500, 'Unprecedented heat across Sahel made worse by climate change', -2.0, 15.0, 1000),
    (2024, '2024 India Heat Wave', 'India', 'North India', 4, 300, 'Extreme pre-monsoon heat exceeding 49C', 77.0, 27.0, 600),
    (1976, '1976 UK Heat Wave', 'United Kingdom', 'UK/Western Europe', 3, 20, 'Prolonged drought and heat across UK summer', -1.0, 52.0, 400),
    (1983, '1983 European Heat Wave', 'France', 'Southern Europe', 3, 300, 'Extended heat across southern Europe with drought', 5.0, 44.0, 600),
    (1987, '1987 Greek Heat Wave', 'Greece', 'Southeast Europe', 4, 1300, 'Intense July heat wave with temperatures above 45C', 24.0, 38.0, 300),
]

KNOWN_COLD_WAVES = [
    (1977, '1977 North American Cold Wave', 'United States', 'Eastern US', 4, 51, 'One of the coldest winters on record for eastern US', -82.0, 38.0, 800),
    (1985, '1985 US Cold Wave', 'United States', 'Central/Eastern US', 4, 126, 'Arctic outbreak with record lows across much of US', -87.0, 38.0, 900),
    (1989, '1989 North American Cold Wave', 'United States', 'Central/Eastern US', 4, 132, 'Intense December cold snap with extreme wind chills', -90.0, 40.0, 1000),
    (1994, '1994 Eastern US Cold Wave', 'United States', 'Eastern US', 3, 70, 'Severe January cold snap affecting eastern states', -80.0, 37.0, 600),
    (1996, '1996 Eastern US Cold Wave', 'United States', 'Eastern US', 3, 154, 'February cold wave with record lows and blizzards', -77.0, 39.0, 700),
    (1999, '1999 Midwest Blizzard & Cold', 'United States', 'Midwest', 3, 68, 'January cold wave and blizzard across the Midwest', -90.0, 42.0, 600),
    (2002, '2002 Mongolian Dzud', 'Mongolia', 'Central Asia', 5, 50, 'Extreme winter killed millions of livestock', 105.0, 47.0, 800),
    (2008, '2008 Afghan Cold Wave', 'Afghanistan', 'Central Asia', 5, 1317, 'Extreme cold killed over 1000 people, mostly in rural areas', 66.0, 35.0, 500),
    (2010, '2010 European Cold Wave', 'Poland', 'Eastern Europe', 4, 650, 'Severe December cold wave across Europe', 20.0, 52.0, 900),
    (2012, '2012 European Cold Wave', 'Ukraine', 'Eastern Europe', 5, 800, 'Extreme February cold wave, -30C across eastern Europe', 30.0, 49.0, 1000),
    (2014, '2014 North American Cold Wave', 'United States', 'Central US', 4, 21, 'Polar vortex brought extreme cold to central US', -88.0, 42.0, 800),
    (2016, '2016 East Asia Cold Wave', 'China', 'East Asia', 4, 85, 'Record cold wave brought snow to tropical regions', 113.0, 30.0, 1000),
    (2018, '2018 European Cold Wave (Beast from the East)', 'United Kingdom', 'Europe', 4, 95, 'Severe cold wave with Siberian air mass across Europe', 0.0, 52.0, 1000),
    (2019, '2019 North American Cold Wave', 'United States', 'Midwest', 4, 22, 'Polar vortex: wind chills below -50C in Chicago', -87.6, 41.9, 700),
    (2021, '2021 Texas Cold Wave (Uri)', 'United States', 'South-Central US', 5, 246, 'Winter Storm Uri caused catastrophic cold, power grid failure in Texas', -97.0, 31.0, 600),
    (2022, '2022 US Winter Storm Elliott', 'United States', 'Eastern US', 4, 87, 'Bomb cyclone with extreme cold across eastern US', -80.0, 42.0, 800),
    (2023, '2023 North American Arctic Blast', 'United States', 'Central US', 3, 90, 'January Arctic outbreak with dangerous wind chills', -90.0, 42.0, 700),
]


def download():
    """Attempt to download climate indices data from NOAA."""
    os.makedirs(RAW_DIR, exist_ok=True)

    urls = {
        'cei.csv': 'https://www.ncei.noaa.gov/access/monitoring/cei/graph/us/01-12/cei.csv',
        'heatwave-index.csv': 'https://www.epa.gov/sites/default/files/2021-04/heatwave_fig-1.csv',
    }

    downloaded = []
    for fname, url in urls.items():
        local_path = os.path.join(RAW_DIR, fname)
        if os.path.exists(local_path):
            print(f"[CLIMATE] Already have {fname}")
            downloaded.append(local_path)
            continue
        print(f"[CLIMATE] Downloading {fname} from {url} ...")
        try:
            resp = requests.get(url, timeout=60, headers={
                'User-Agent': 'Mozilla/5.0 (disaster-data-pipeline)'
            })
            resp.raise_for_status()
            with open(local_path, 'w') as f:
                f.write(resp.text)
            downloaded.append(local_path)
            print(f"[CLIMATE] Saved {local_path}")
        except requests.RequestException as e:
            print(f"[CLIMATE] WARNING: Could not download {fname}: {e}")

    print(f"[CLIMATE] Downloaded {len(downloaded)} files. Curated event lists always available as fallback.")
    return downloaded


def generate_event_polygon(center_lon, center_lat, radius_km):
    """Generate irregular polygon for a climate event.
    Adds slight random perturbations to make polygons look more natural.
    Uses a deterministic seed based on coordinates for reproducibility.
    """
    seed = int(abs(center_lon * 1000) + abs(center_lat * 1000))
    rng = random.Random(seed)

    num_points = 24
    coords = []
    earth_radius_km = 6371.0
    lat_rad = math.radians(center_lat)

    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        perturbation = 0.75 + rng.random() * 0.5
        r = radius_km * perturbation

        dlat = (r / earth_radius_km) * math.cos(angle)
        dlon = (r / (earth_radius_km * max(math.cos(lat_rad), 0.01))) * math.sin(angle)
        pt_lat = _clamp_lat(center_lat + math.degrees(dlat))
        pt_lon = _clamp_lon(center_lon + math.degrees(dlon))
        coords.append([pt_lon, pt_lat])

    coords.append(coords[0])
    return coords


def load(min_year=1976):
    """Load climate extreme events.
    Try raw data first, fall back to curated lists.
    Return features for heatwaves, cold waves.
    Create polygon features using buffer_point for approximate affected regions.
    """
    features = []

    raw_features = _load_raw_data(min_year)
    if raw_features:
        features.extend(raw_features)
        print(f"[CLIMATE] Loaded {len(raw_features)} features from raw data.")

    hw_features = load_heatwaves(min_year)
    cw_features = load_cold_waves(min_year)

    raw_hw_names = {f['properties'].get('name') for f in features if f['properties'].get('type') == 'heat_wave'}
    raw_cw_names = {f['properties'].get('name') for f in features if f['properties'].get('type') == 'cold_wave'}

    for f in hw_features:
        if f['properties'].get('name') not in raw_hw_names:
            features.append(f)

    for f in cw_features:
        if f['properties'].get('name') not in raw_cw_names:
            features.append(f)

    print(f"[CLIMATE] Total climate extreme features: {len(features)}")
    return features


def load_heatwaves(min_year=1976):
    """Load/generate heatwave features."""
    features = []
    print(f"[CLIMATE] Generating {len(KNOWN_HEATWAVES)} curated heatwave events...")

    for entry in KNOWN_HEATWAVES:
        year, name, country, region, severity, deaths, description, lon, lat, radius_km = entry
        if year < min_year:
            continue

        props = {
            'name': name,
            'type': 'heat_wave',
            'year': year,
            'start_date': f"{year}-06-01",
            'end_date': f"{year}-08-31",
            'country': normalize_country(country),
            'region': region,
            'severity': severity,
            'deaths': deaths,
            'description': description,
            'source': 'Curated climate records',
        }

        coords = generate_event_polygon(lon, lat, radius_km)
        feat = polygon_feature(coords, props)
        features.append(feat)

    print(f"[CLIMATE] Generated {len(features)} heatwave features.")
    return features


def load_cold_waves(min_year=1976):
    """Load/generate cold wave features."""
    features = []
    print(f"[CLIMATE] Generating {len(KNOWN_COLD_WAVES)} curated cold wave events...")

    for entry in KNOWN_COLD_WAVES:
        year, name, country, region, severity, deaths, description, lon, lat, radius_km = entry
        if year < min_year:
            continue

        props = {
            'name': name,
            'type': 'cold_wave',
            'year': year,
            'start_date': f"{year}-01-01",
            'end_date': f"{year}-02-28",
            'country': normalize_country(country),
            'region': region,
            'severity': severity,
            'deaths': deaths,
            'description': description,
            'source': 'Curated climate records',
        }

        coords = generate_event_polygon(lon, lat, radius_km)
        feat = polygon_feature(coords, props)
        features.append(feat)

    print(f"[CLIMATE] Generated {len(features)} cold wave features.")
    return features


def _load_raw_data(min_year):
    """Attempt to load climate data from raw files in RAW_DIR."""
    features = []

    for fpath in glob.glob(os.path.join(RAW_DIR, '*.geojson')) + glob.glob(os.path.join(RAW_DIR, '*.json')):
        print(f"[CLIMATE] Reading raw file: {fpath}")
        try:
            with open(fpath) as f:
                data = json.load(f)
            if data.get('type') == 'FeatureCollection':
                for feat in data.get('features', []):
                    yr = parse_int(feat.get('properties', {}).get('year'))
                    if yr is not None and yr < min_year:
                        continue
                    feat.setdefault('properties', {})['source'] = 'Raw climate data'
                    features.append(feat)
                print(f"[CLIMATE] Loaded {len(features)} features from {fpath}")
            elif data.get('type') == 'Feature':
                data.setdefault('properties', {})['source'] = 'Raw climate data'
                features.append(data)
        except Exception as e:
            print(f"[CLIMATE] WARNING: Could not read {fpath}: {e}")

    for fpath in glob.glob(os.path.join(RAW_DIR, '*.csv')):
        print(f"[CLIMATE] Reading raw CSV: {fpath}")
        try:
            df = pd.read_csv(fpath, low_memory=False)
            cols_lower = {c.lower(): c for c in df.columns}

            lat_col = None
            lon_col = None
            for name in ['latitude', 'lat']:
                if name in cols_lower:
                    lat_col = cols_lower[name]
                    break
            for name in ['longitude', 'lon', 'long']:
                if name in cols_lower:
                    lon_col = cols_lower[name]
                    break

            if lat_col and lon_col:
                for _, row in df.iterrows():
                    lat = parse_float(row.get(lat_col))
                    lon = parse_float(row.get(lon_col))
                    if lat is not None and lon is not None:
                        yr_col = cols_lower.get('year')
                        yr = parse_int(row.get(yr_col)) if yr_col else None
                        if yr is not None and yr < min_year:
                            continue
                        props = {}
                        for col in df.columns:
                            val = clean_string(row.get(col))
                            if val is not None:
                                props[col] = val
                        props['source'] = 'Raw climate CSV'
                        features.append(point_feature(lon, lat, props))
                print(f"[CLIMATE] Loaded {len(features)} features from {fpath}")
        except Exception as e:
            print(f"[CLIMATE] WARNING: Could not read {fpath}: {e}")

    return features


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Climate extremes importer')
    parser.add_argument('--download', action='store_true', help='Download climate indices')
    parser.add_argument('--min-year', type=int, default=1976)
    args = parser.parse_args()

    if args.download:
        download()

    features = load(min_year=args.min_year)
    print(f"Total climate features: {len(features)}")
    if features:
        types = {}
        for f in features:
            t = f['properties'].get('type', 'unknown')
            types[t] = types.get(t, 0) + 1
        for t, c in sorted(types.items()):
            print(f"  {t}: {c}")
