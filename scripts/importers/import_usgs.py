"""
USGS Earthquake Catalog importer.
Downloads/reads earthquake data from USGS ComCat API.
API: https://earthquake.usgs.gov/fdsnws/event/1/query

Usage:
    python import_usgs.py --download          # download raw CSVs
    python import_usgs.py --download --min-year 2000 --min-mag 6.0
    python import_usgs.py                     # load & parse cached files
    python import_usgs.py --min-year 2010     # load with filters
"""

import os
import sys
import glob
import argparse
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.normalize import *
from scripts.utils.geo import *

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'raw', 'usgs')
API_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query'


def download(min_year=1976, max_year=None, min_magnitude=5.0):
    """Download earthquake CSV from USGS API in yearly chunks (API limits 20k rows).
    Save to raw/usgs/usgs_earthquakes_YYYY.csv.
    """
    import requests

    os.makedirs(RAW_DIR, exist_ok=True)

    if max_year is None:
        max_year = datetime.now().year

    print(f"[USGS] Downloading earthquakes M{min_magnitude}+ from {min_year} to {max_year}")

    for year in range(min_year, max_year + 1):
        out_path = os.path.join(RAW_DIR, f'usgs_earthquakes_{year}.csv')
        if os.path.exists(out_path):
            print(f"  {year}: already exists, skipping ({out_path})")
            continue

        params = {
            'format': 'csv',
            'starttime': f'{year}-01-01',
            'endtime': f'{year + 1}-01-01',
            'minmagnitude': min_magnitude,
            'orderby': 'time',
            'limit': 20000,
        }

        print(f"  {year}: requesting...", end=' ', flush=True)
        try:
            resp = requests.get(API_URL, params=params, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"FAILED ({e})")
            continue

        row_count = len(resp.text.strip().split('\n')) - 1
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        print(f"OK ({row_count} rows)")

        time.sleep(0.5)

    print("[USGS] Download complete.")


def extract_country_from_place(place_str):
    """Extract country name from USGS place string like '10 km NNE of Tocopilla, Chile'.
    Usually the last part after the final comma. US states/territories are mapped
    to 'United States'.
    """
    if not place_str:
        return None
    place = str(place_str).strip()

    us_regions = {
        'alaska', 'hawaii', 'california', 'oklahoma', 'nevada', 'washington',
        'oregon', 'montana', 'wyoming', 'utah', 'idaho', 'tennessee',
        'missouri', 'arkansas', 'texas', 'kansas', 'puerto rico',
        'us virgin islands', 'guam', 'american samoa', 'northern mariana islands',
        'new york', 'south carolina', 'north carolina', 'virginia', 'west virginia',
        'kentucky', 'ohio', 'illinois', 'michigan', 'minnesota', 'wisconsin',
        'iowa', 'nebraska', 'colorado', 'new mexico', 'arizona', 'connecticut',
        'maine', 'massachusetts', 'new hampshire', 'rhode island', 'vermont',
        'new jersey', 'pennsylvania', 'delaware', 'maryland', 'georgia',
        'florida', 'alabama', 'mississippi', 'louisiana', 'indiana',
        'south dakota', 'north dakota',
    }

    if ',' in place:
        tail = place.rsplit(',', 1)[-1].strip()
        if tail.lower() in us_regions:
            return 'United States'
        return normalize_country(tail) if tail else None

    place_lower = place.lower()
    for region in us_regions:
        if region in place_lower:
            return 'United States'
    return None


def _clamp(val, lo, hi):
    return max(lo, min(hi, float(val)))


def load(min_year=1976, min_magnitude=5.0):
    """Load all CSV files from raw/usgs/, parse, normalize, return GeoJSON features."""
    import pandas as pd

    csv_files = sorted(glob.glob(os.path.join(RAW_DIR, 'usgs_earthquakes_*.csv')))
    if not csv_files:
        print(f"[USGS] No CSV files found in {RAW_DIR}. Run with --download first.")
        return []

    print(f"[USGS] Loading {len(csv_files)} CSV files from {RAW_DIR}")

    frames = []
    for fpath in csv_files:
        try:
            df = pd.read_csv(fpath, dtype=str)
            if df.empty:
                continue
            frames.append(df)
        except Exception as e:
            print(f"  WARNING: Could not read {fpath}: {e}")
            continue

    if not frames:
        print("[USGS] No valid data loaded.")
        return []

    df = pd.concat(frames, ignore_index=True)
    print(f"[USGS] Total raw rows: {len(df)}")

    for col in ('latitude', 'longitude', 'depth', 'mag'):
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['latitude', 'longitude', 'mag'])

    if min_magnitude is not None:
        df = df[df['mag'] >= min_magnitude]

    features = []
    skipped = 0

    for _, row in df.iterrows():
        try:
            lat = parse_float(row.get('latitude'))
            lon = parse_float(row.get('longitude'))
            mag = parse_float(row.get('mag'))

            if lat is None or lon is None or mag is None:
                skipped += 1
                continue

            lat = _clamp(lat, -90.0, 90.0)
            lon = _clamp(lon, -180.0, 180.0)

            place = clean_string(row.get('place')) or ''
            usgs_id = clean_string(row.get('id')) or ''
            mag_type = clean_string(row.get('magType')) or 'ml'
            eq_type = clean_string(row.get('type')) or 'earthquake'
            depth = parse_float(row.get('depth'))
            time_str = clean_string(row.get('time'))

            date_parsed = parse_date(time_str)
            year = parse_year(time_str)

            if min_year and year and year < min_year:
                continue

            country = extract_country_from_place(place)
            region = extract_country_from_place(place)

            event_id = slugify_id('eq', year, usgs_id or f'{lat}_{lon}_{mag}')

            properties = {
                'id': event_id,
                'name': place or f"M{mag} Earthquake",
                'type': 'earthquake',
                'subtype': eq_type,
                'year': parse_int(year),
                'start_date': date_parsed,
                'country': country,
                'region': region,
                'latitude': lat,
                'longitude': lon,
                'depth_km': depth,
                'severity': mag,
                'severity_unit': mag_type,
                'deaths': None,
                'source': 'USGS',
                'source_id': usgs_id,
            }

            features.append(point_feature(lon, lat, properties))

            if mag >= 6.0:
                radius_km = magnitude_to_radius_km(mag)
                ring_coords = buffer_point(lon, lat, radius_km)
                ring_props = dict(properties)
                ring_props['id'] = event_id + '_radius'
                ring_props['feature_type'] = 'impact_radius'
                ring_props['radius_km'] = radius_km
                features.append(polygon_feature(ring_coords, ring_props))

        except Exception as e:
            skipped += 1
            continue

    print(f"[USGS] Produced {len(features)} features ({skipped} rows skipped)")
    return features


def main():
    parser = argparse.ArgumentParser(description='USGS Earthquake Catalog importer')
    parser.add_argument('--download', action='store_true', help='Download raw CSV files from USGS API')
    parser.add_argument('--min-year', type=int, default=1976, help='Minimum year (default: 1976)')
    parser.add_argument('--max-year', type=int, default=None, help='Maximum year (default: current)')
    parser.add_argument('--min-mag', type=float, default=5.0, help='Minimum magnitude (default: 5.0)')
    parser.add_argument('--output', type=str, default=None, help='Write GeoJSON output to file')
    args = parser.parse_args()

    if args.download:
        download(min_year=args.min_year, max_year=args.max_year, min_magnitude=args.min_mag)

    features = load(min_year=args.min_year, min_magnitude=args.min_mag)
    print(f"[USGS] {len(features)} total features returned")

    if args.output and features:
        import json
        collection = {
            'type': 'FeatureCollection',
            'features': features,
        }
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(collection, f, ensure_ascii=False)
        print(f"[USGS] Wrote {args.output}")

    return features


if __name__ == '__main__':
    main()
