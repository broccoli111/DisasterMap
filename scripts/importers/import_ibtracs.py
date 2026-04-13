"""
IBTrACS (International Best Track Archive) importer.
Downloads/reads tropical cyclone track data from NCEI.

URL: https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv

Usage:
    python import_ibtracs.py --download       # download full IBTrACS CSV
    python import_ibtracs.py                  # load & parse cached file
    python import_ibtracs.py --min-year 2000  # load with year filter
"""

import os
import sys
import glob
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.normalize import *
from scripts.utils.geo import *

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'raw', 'ibtracs')
DOWNLOAD_URL = (
    'https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/'
    'v04r01/access/csv/ibtracs.ALL.list.v04r01.csv'
)

BASIN_NAMES = {
    'NA': 'North Atlantic',
    'SA': 'South Atlantic',
    'EP': 'Eastern Pacific',
    'WP': 'Western Pacific',
    'NI': 'North Indian',
    'SI': 'South Indian',
    'SP': 'South Pacific',
    'MM': 'Multiple Basins',
    'AS': 'Arabian Sea',
    'BB': 'Bay of Bengal',
    'EA': 'Eastern Australia',
    'WA': 'Western Australia',
}

CATEGORY_NAMES = {
    -5: 'Unknown',
    -4: 'Post-tropical',
    -3: 'Miscellaneous',
    -2: 'Subtropical',
    -1: 'Tropical Depression',
    0: 'Tropical Storm',
    1: 'Category 1',
    2: 'Category 2',
    3: 'Category 3',
    4: 'Category 4',
    5: 'Category 5',
}


def basin_to_region(basin):
    """Map IBTrACS basin codes to human-readable region names."""
    if not basin:
        return 'Unknown'
    return BASIN_NAMES.get(str(basin).strip().upper(), str(basin).strip())


def wind_to_category(wind_kt):
    """Convert max sustained wind (knots) to Saffir-Simpson category integer.
    TD<34, TS 34-63, Cat1 64-82, Cat2 83-95, Cat3 96-112, Cat4 113-136, Cat5 137+
    Returns integer: -1 (TD), 0 (TS), 1-5 (hurricane categories).
    """
    w = parse_float(wind_kt)
    if w is None:
        return -5
    if w < 34:
        return -1
    elif w < 64:
        return 0
    elif w < 83:
        return 1
    elif w < 96:
        return 2
    elif w < 113:
        return 3
    elif w < 137:
        return 4
    else:
        return 5


def category_label(cat_int):
    """Convert numeric category to human-readable label."""
    return CATEGORY_NAMES.get(cat_int, f'Category {cat_int}' if cat_int and cat_int > 0 else 'Unknown')


def download():
    """Download the full IBTrACS CSV (~200MB). Save to raw/ibtracs/."""
    import requests

    os.makedirs(RAW_DIR, exist_ok=True)
    out_path = os.path.join(RAW_DIR, 'ibtracs.ALL.list.v04r01.csv')

    if os.path.exists(out_path):
        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        print(f"[IBTrACS] File already exists: {out_path} ({size_mb:.1f} MB)")
        print("  Delete it manually to re-download.")
        return out_path

    print(f"[IBTrACS] Downloading full IBTrACS dataset...")
    print(f"  URL: {DOWNLOAD_URL}")
    print("  This may take several minutes for ~200 MB...")

    try:
        resp = requests.get(DOWNLOAD_URL, stream=True, timeout=600)
        resp.raise_for_status()

        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        chunk_size = 1024 * 1024

        with open(out_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        pct = downloaded / total_size * 100
                        print(f"\r  {downloaded / (1024*1024):.1f} / {total_size / (1024*1024):.1f} MB ({pct:.0f}%)", end='', flush=True)
                    else:
                        print(f"\r  {downloaded / (1024*1024):.1f} MB downloaded", end='', flush=True)

        print(f"\n[IBTrACS] Saved to {out_path}")
        return out_path

    except Exception as e:
        print(f"\n[IBTrACS] Download FAILED: {e}")
        if os.path.exists(out_path):
            os.remove(out_path)
        return None


def _find_csv():
    """Locate the IBTrACS CSV file in RAW_DIR."""
    candidates = glob.glob(os.path.join(RAW_DIR, 'ibtracs*.csv'))
    if not candidates:
        return None
    return sorted(candidates, key=os.path.getsize, reverse=True)[0]


def _clamp_lat(v):
    return max(-90.0, min(90.0, float(v)))


def _clamp_lon(v):
    return max(-180.0, min(180.0, float(v)))


def load(min_year=1976):
    """Load IBTrACS CSV, group track points by storm (SID column), build LineString tracks.
    Returns list of GeoJSON Feature dicts.
    """
    import pandas as pd

    csv_path = _find_csv()
    if not csv_path:
        print(f"[IBTrACS] No CSV found in {RAW_DIR}. Run with --download first.")
        return []

    print(f"[IBTrACS] Loading {csv_path}")
    try:
        df = pd.read_csv(
            csv_path,
            dtype=str,
            low_memory=False,
            skiprows=[1],
            na_values=[' ', ''],
            keep_default_na=True,
        )
    except Exception as e:
        print(f"[IBTrACS] Failed to read CSV: {e}")
        return []

    print(f"[IBTrACS] Raw rows: {len(df)}")

    required_cols = ['SID', 'LAT', 'LON']
    for col in required_cols:
        if col not in df.columns:
            print(f"[IBTrACS] Missing required column: {col}")
            return []

    df['LAT'] = pd.to_numeric(df['LAT'], errors='coerce')
    df['LON'] = pd.to_numeric(df['LON'], errors='coerce')
    df = df.dropna(subset=['LAT', 'LON'])

    if 'USA_WIND' in df.columns:
        df['USA_WIND'] = pd.to_numeric(df['USA_WIND'], errors='coerce')
    if 'USA_PRES' in df.columns:
        df['USA_PRES'] = pd.to_numeric(df['USA_PRES'], errors='coerce')
    if 'USA_SSHS' in df.columns:
        df['USA_SSHS'] = pd.to_numeric(df['USA_SSHS'], errors='coerce')

    features = []
    skipped = 0
    grouped = df.groupby('SID', sort=False)
    total_storms = len(grouped)
    print(f"[IBTrACS] Processing {total_storms} storms...")

    for storm_idx, (sid, group) in enumerate(grouped):
        try:
            if storm_idx % 5000 == 0 and storm_idx > 0:
                print(f"  ... processed {storm_idx}/{total_storms} storms")

            season = parse_int(group['SEASON'].iloc[0]) if 'SEASON' in group.columns else None
            if min_year and season and season < min_year:
                continue

            name_raw = clean_string(group['NAME'].iloc[0]) if 'NAME' in group.columns else None
            storm_name = name_raw if name_raw and name_raw.upper() not in ('NOT_NAMED', 'UNNAMED', 'NONAME') else None

            basin = clean_string(group['BASIN'].iloc[0]) if 'BASIN' in group.columns else None

            coords = []
            for _, pt in group.iterrows():
                lat = parse_float(pt['LAT'])
                lon = parse_float(pt['LON'])
                if lat is not None and lon is not None:
                    coords.append([_clamp_lon(lon), _clamp_lat(lat)])

            if len(coords) < 3:
                skipped += 1
                continue

            max_wind = None
            if 'USA_WIND' in group.columns:
                wind_vals = group['USA_WIND'].dropna()
                if len(wind_vals) > 0:
                    max_wind = wind_vals.max()

            min_pressure = None
            if 'USA_PRES' in group.columns:
                pres_vals = group['USA_PRES'].dropna()
                if len(pres_vals) > 0:
                    min_pressure = pres_vals.min()

            max_cat = None
            if 'USA_SSHS' in group.columns:
                cat_vals = group['USA_SSHS'].dropna()
                if len(cat_vals) > 0:
                    max_cat = int(cat_vals.max())
            if max_cat is None and max_wind is not None:
                max_cat = wind_to_category(max_wind)

            first_time = clean_string(group['ISO_TIME'].iloc[0]) if 'ISO_TIME' in group.columns else None
            start_date = parse_date(first_time)
            last_time = clean_string(group['ISO_TIME'].iloc[-1]) if 'ISO_TIME' in group.columns else None
            end_date = parse_date(last_time)

            display_name = storm_name.title() if storm_name else f"Unnamed ({sid})"
            cat_str = category_label(max_cat) if max_cat is not None else 'Unknown'

            event_id = slugify_id('tc', season, storm_name or str(sid))

            properties = {
                'id': event_id,
                'name': display_name,
                'type': 'hurricane',
                'subtype': cat_str,
                'year': season,
                'start_date': start_date,
                'end_date': end_date,
                'country': None,
                'region': basin_to_region(basin),
                'basin': clean_string(basin),
                'severity': parse_float(max_wind),
                'severity_unit': 'knots (max sustained wind)',
                'category': max_cat,
                'category_label': cat_str,
                'min_pressure_mb': parse_float(min_pressure),
                'track_points': len(coords),
                'deaths': None,
                'source': 'IBTrACS',
                'source_id': str(sid),
            }

            features.append(line_feature(coords, properties))

        except Exception as e:
            skipped += 1
            continue

    print(f"[IBTrACS] Produced {len(features)} features ({skipped} storms skipped)")
    return features


def main():
    parser = argparse.ArgumentParser(description='IBTrACS Tropical Cyclone importer')
    parser.add_argument('--download', action='store_true', help='Download full IBTrACS CSV')
    parser.add_argument('--min-year', type=int, default=1976, help='Minimum season year (default: 1976)')
    parser.add_argument('--output', type=str, default=None, help='Write GeoJSON output to file')
    args = parser.parse_args()

    if args.download:
        download()

    features = load(min_year=args.min_year)
    print(f"[IBTrACS] {len(features)} total features returned")

    if args.output and features:
        import json
        collection = {
            'type': 'FeatureCollection',
            'features': features,
        }
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(collection, f, ensure_ascii=False)
        print(f"[IBTrACS] Wrote {args.output}")

    return features


if __name__ == '__main__':
    main()
