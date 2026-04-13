"""
NOAA Storm Events Database importer.
Covers: tornadoes, ice storms, blizzards, winter storms, cold waves.
Data: https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/
Files: StormEvents_details-ftp_v1.0_dYYYY*.csv.gz
"""

import os
import sys
import re
import gzip
import glob
import math
from collections import defaultdict

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

RAW_DIR = 'raw/tornadoes'
BASE_URL = 'https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'

EVENT_TYPE_MAP = {
    'Tornado': 'tornado',
    'Ice Storm': 'ice_storm',
    'Blizzard': 'blizzard',
    'Winter Storm': 'blizzard',
    'Heavy Snow': 'blizzard',
    'Cold/Wind Chill': 'cold_wave',
    'Extreme Cold/Wind Chill': 'cold_wave',
    'Frost/Freeze': 'cold_wave',
}


def download(min_year=1976):
    """Download NOAA Storm Events detail CSV files.
    Files are named like StormEvents_details-ftp_v1.0_dYYYY_cYYYYMMDD.csv.gz
    Download from the NCEI FTP-style HTTP directory listing.
    """
    os.makedirs(RAW_DIR, exist_ok=True)
    print(f"[NOAA] Fetching directory listing from {BASE_URL}")
    try:
        resp = requests.get(BASE_URL, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[NOAA] WARNING: Could not fetch directory listing: {e}")
        return []

    pattern = re.compile(r'(StormEvents_details-ftp_v1\.0_d(\d{4})_c\d{8}\.csv\.gz)')
    matches = pattern.findall(resp.text)
    if not matches:
        print("[NOAA] WARNING: No detail files found in directory listing.")
        return []

    best_per_year = {}
    for filename, year_str in matches:
        year = int(year_str)
        if year < min_year:
            continue
        if year not in best_per_year or filename > best_per_year[year]:
            best_per_year[year] = filename

    downloaded = []
    for year in sorted(best_per_year):
        filename = best_per_year[year]
        local_path = os.path.join(RAW_DIR, filename)
        if os.path.exists(local_path):
            print(f"[NOAA] Already have {filename}")
            downloaded.append(local_path)
            continue
        url = BASE_URL + filename
        print(f"[NOAA] Downloading {filename} ...")
        try:
            r = requests.get(url, timeout=120, stream=True)
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            downloaded.append(local_path)
            print(f"[NOAA] Saved {local_path}")
        except requests.RequestException as e:
            print(f"[NOAA] WARNING: Failed to download {filename}: {e}")

    print(f"[NOAA] Downloaded {len(downloaded)} files.")
    return downloaded


def parse_damage(val):
    """Parse NOAA damage strings like '10K', '1.5M', '2B' into USD."""
    if val is None:
        return 0.0
    val = str(val).strip().upper()
    if not val or val in ('NAN', 'NONE', ''):
        return 0.0
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}
    m = re.match(r'^([0-9]*\.?[0-9]+)\s*([KMB])?$', val)
    if m:
        number = float(m.group(1))
        suffix = m.group(2)
        return number * multipliers.get(suffix, 1)
    try:
        return float(val)
    except ValueError:
        return 0.0


def load(min_year=1976, event_types=None):
    """Load storm events CSVs, filter by type, create features.

    Key columns: EVENT_TYPE, BEGIN_YEARMONTH, BEGIN_DAY, END_YEARMONTH, END_DAY,
                 STATE, CZ_NAME, BEGIN_LAT, BEGIN_LON, END_LAT, END_LON,
                 INJURIES_DIRECT, DEATHS_DIRECT, DAMAGE_PROPERTY,
                 TOR_F_SCALE, TOR_LENGTH, TOR_WIDTH, EVENT_NARRATIVE

    For tornadoes: Create LineString from BEGIN to END coords
    For ice/blizzard/cold: Create polygon from state/CZ boundaries (approximate with point + buffer)
    Aggregate small events by state+month into larger regional events
    """
    if event_types is None:
        event_types = set(EVENT_TYPE_MAP.values())
    else:
        event_types = set(event_types)

    csv_files = sorted(glob.glob(os.path.join(RAW_DIR, 'StormEvents_details*.csv.gz')))
    plain_csvs = sorted(glob.glob(os.path.join(RAW_DIR, 'StormEvents_details*.csv')))
    csv_files.extend([f for f in plain_csvs if not f.endswith('.gz')])

    if not csv_files:
        print(f"[NOAA] No storm events files found in {RAW_DIR}/")
        return _load_fallback(min_year, event_types)

    all_tornado_features = []
    winter_events_raw = defaultdict(list)

    print(f"[NOAA] Processing {len(csv_files)} files...")
    for filepath in csv_files:
        year_match = re.search(r'_d(\d{4})', filepath)
        if year_match:
            file_year = int(year_match.group(1))
            if file_year < min_year:
                continue

        try:
            if filepath.endswith('.gz'):
                df = pd.read_csv(filepath, compression='gzip', low_memory=False)
            else:
                df = pd.read_csv(filepath, low_memory=False)
        except Exception as e:
            print(f"[NOAA] WARNING: Could not read {filepath}: {e}")
            continue

        if 'EVENT_TYPE' not in df.columns:
            print(f"[NOAA] WARNING: No EVENT_TYPE column in {filepath}, skipping.")
            continue

        df = df[df['EVENT_TYPE'].isin(EVENT_TYPE_MAP.keys())]
        if df.empty:
            continue

        for _, row in df.iterrows():
            noaa_type = clean_string(row.get('EVENT_TYPE'))
            if noaa_type is None:
                continue
            our_type = EVENT_TYPE_MAP.get(noaa_type)
            if our_type is None or our_type not in event_types:
                continue

            begin_ym = clean_string(row.get('BEGIN_YEARMONTH'))
            begin_day = parse_int(row.get('BEGIN_DAY'), 1)
            end_ym = clean_string(row.get('END_YEARMONTH'))
            end_day = parse_int(row.get('END_DAY'), 1)

            if begin_ym and len(str(begin_ym)) >= 6:
                year = int(str(begin_ym)[:4])
                month = int(str(begin_ym)[4:6])
            else:
                continue

            if year < min_year:
                continue

            start_date = f"{year:04d}-{month:02d}-{begin_day:02d}"
            if end_ym and len(str(end_ym)) >= 6:
                end_year = int(str(end_ym)[:4])
                end_month = int(str(end_ym)[4:6])
                end_date = f"{end_year:04d}-{end_month:02d}-{end_day:02d}"
            else:
                end_date = start_date

            state = clean_string(row.get('STATE')) or 'Unknown'
            cz_name = clean_string(row.get('CZ_NAME')) or ''
            begin_lat = parse_float(row.get('BEGIN_LAT'))
            begin_lon = parse_float(row.get('BEGIN_LON'))
            end_lat = parse_float(row.get('END_LAT'))
            end_lon = parse_float(row.get('END_LON'))
            injuries = parse_int(row.get('INJURIES_DIRECT'), 0)
            deaths = parse_int(row.get('DEATHS_DIRECT'), 0)
            damage = parse_damage(row.get('DAMAGE_PROPERTY'))
            narrative = clean_string(row.get('EVENT_NARRATIVE')) or ''
            episode_narrative = clean_string(row.get('EPISODE_NARRATIVE')) or ''

            if our_type == 'tornado':
                tor_scale = clean_string(row.get('TOR_F_SCALE')) or ''
                tor_length = parse_float(row.get('TOR_LENGTH'), 0)
                tor_width = parse_float(row.get('TOR_WIDTH'), 0)

                props = {
                    'name': f"{state.title()} Tornado {start_date}",
                    'type': 'tornado',
                    'year': year,
                    'start_date': start_date,
                    'end_date': end_date,
                    'country': 'United States',
                    'state': state.title() if state else None,
                    'county': cz_name.title() if cz_name else None,
                    'deaths': deaths,
                    'injuries': injuries,
                    'damage_usd': damage,
                    'fujita_scale': tor_scale,
                    'path_length_mi': tor_length,
                    'path_width_yd': tor_width,
                    'narrative': narrative or episode_narrative,
                    'source': 'NOAA Storm Events Database',
                }

                if begin_lat and begin_lon and end_lat and end_lon:
                    blat = _clamp_lat(begin_lat)
                    blon = _clamp_lon(begin_lon)
                    elat = _clamp_lat(end_lat)
                    elon = _clamp_lon(end_lon)
                    if abs(blat - elat) > 0.001 or abs(blon - elon) > 0.001:
                        feat = line_feature([[blon, blat], [elon, elat]], props)
                    else:
                        feat = point_feature(blon, blat, props)
                elif begin_lat and begin_lon:
                    feat = point_feature(_clamp_lon(begin_lon), _clamp_lat(begin_lat), props)
                else:
                    continue

                all_tornado_features.append(feat)
            else:
                event_data = {
                    'noaa_type': noaa_type,
                    'our_type': our_type,
                    'state': state,
                    'cz_name': cz_name,
                    'year': year,
                    'month': month,
                    'start_date': start_date,
                    'end_date': end_date,
                    'lat': begin_lat,
                    'lon': begin_lon,
                    'deaths': deaths,
                    'injuries': injuries,
                    'damage': damage,
                    'narrative': narrative or episode_narrative,
                }
                key = (our_type, state, year, month)
                winter_events_raw[key].append(event_data)

    winter_features = []
    for event_type in ['ice_storm', 'blizzard', 'cold_wave']:
        type_events = {k: v for k, v in winter_events_raw.items() if k[0] == event_type}
        winter_features.extend(aggregate_winter_events(type_events, event_type))

    features = all_tornado_features + winter_features
    print(f"[NOAA] Loaded {len(all_tornado_features)} tornado features, {len(winter_features)} winter event features.")
    return features


def aggregate_winter_events(events_by_key, event_type):
    """Group small winter events by state+year+month into regional events.
    Creates polygon features covering the affected region.
    """
    features = []
    type_labels = {
        'ice_storm': 'Ice Storm',
        'blizzard': 'Blizzard/Winter Storm',
        'cold_wave': 'Cold Wave',
    }

    for (etype, state, year, month), records in events_by_key.items():
        if not records:
            continue

        lats = [r['lat'] for r in records if r['lat'] is not None]
        lons = [r['lon'] for r in records if r['lon'] is not None]
        total_deaths = sum(r['deaths'] for r in records)
        total_injuries = sum(r['injuries'] for r in records)
        total_damage = sum(r['damage'] for r in records)
        narratives = [r['narrative'] for r in records if r['narrative']]

        dates_start = sorted([r['start_date'] for r in records])
        dates_end = sorted([r['end_date'] for r in records])

        label = type_labels.get(event_type, event_type.replace('_', ' ').title())

        props = {
            'name': f"{state.title()} {label} {year}-{month:02d}",
            'type': event_type,
            'year': year,
            'start_date': dates_start[0] if dates_start else None,
            'end_date': dates_end[-1] if dates_end else None,
            'country': 'United States',
            'state': state.title() if state else None,
            'deaths': total_deaths,
            'injuries': total_injuries,
            'damage_usd': total_damage,
            'event_count': len(records),
            'narrative': narratives[0] if narratives else None,
            'source': 'NOAA Storm Events Database',
        }

        if lats and lons:
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)

            if len(lats) >= 3:
                lat_spread = max(lats) - min(lats)
                lon_spread = max(lons) - min(lons)
                radius_km = max(50, math.sqrt(lat_spread ** 2 + lon_spread ** 2) * 111 / 2)
            else:
                radius_km = 75.0

            coords = buffer_point(center_lon, center_lat, min(radius_km, 500))
            feat = polygon_feature(coords, props)
        else:
            continue

        features.append(feat)

    return features


def _load_fallback(min_year, event_types):
    """Attempt to load any CSV or GeoJSON files from the raw directory."""
    import json as _json
    features = []

    for pattern in ['*.csv', '*.geojson', '*.json']:
        for fpath in glob.glob(os.path.join(RAW_DIR, pattern)):
            print(f"[NOAA] Trying fallback file: {fpath}")
            try:
                if fpath.endswith('.csv'):
                    df = pd.read_csv(fpath, low_memory=False)
                    for _, row in df.iterrows():
                        lat = parse_float(row.get('latitude') or row.get('lat') or row.get('BEGIN_LAT'))
                        lon = parse_float(row.get('longitude') or row.get('lon') or row.get('BEGIN_LON'))
                        if lat and lon:
                            props = {k: clean_string(v) for k, v in row.to_dict().items()}
                            props['source'] = 'NOAA (fallback CSV)'
                            features.append(point_feature(lon, lat, props))
                else:
                    with open(fpath) as f:
                        data = _json.load(f)
                    if data.get('type') == 'FeatureCollection':
                        features.extend(data.get('features', []))
                    elif data.get('type') == 'Feature':
                        features.append(data)
            except Exception as e:
                print(f"[NOAA] WARNING: Could not read fallback {fpath}: {e}")

    print(f"[NOAA] Fallback loaded {len(features)} features.")
    return features


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='NOAA Storm Events importer')
    parser.add_argument('--download', action='store_true', help='Download data files')
    parser.add_argument('--min-year', type=int, default=1976)
    args = parser.parse_args()

    if args.download:
        download(min_year=args.min_year)

    features = load(min_year=args.min_year)
    print(f"Total features: {len(features)}")
    if features:
        types_count = defaultdict(int)
        for f in features:
            types_count[f['properties'].get('type', 'unknown')] += 1
        for t, c in sorted(types_count.items()):
            print(f"  {t}: {c}")
