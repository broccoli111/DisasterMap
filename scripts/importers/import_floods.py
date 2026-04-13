"""
Flood data importer.
Primary: Dartmouth Flood Observatory (DFO) Global Active Archive of Large Flood Events.
URL: https://floodobservatory.colorado.edu/Archives/index.html
Data format: Excel/CSV with columns for dates, location, severity, deaths, coordinates.
"""

import os
import sys
import re
import glob
import json
import math

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.normalize import *
from scripts.utils.geo import *

RAW_DIR = 'raw/floods'
DFO_URL = 'https://floodobservatory.colorado.edu/Archives/index.html'

DFO_EXCEL_URLS = [
    'https://floodobservatory.colorado.edu/Archives/MasterListrev.xlsx',
    'https://floodobservatory.colorado.edu/Archives/MasterList.xlsx',
]


def download():
    """Download DFO flood archive. Format may be Excel (.xlsx) or CSV."""
    os.makedirs(RAW_DIR, exist_ok=True)

    for url in DFO_EXCEL_URLS:
        filename = url.rsplit('/', 1)[-1]
        local_path = os.path.join(RAW_DIR, filename)
        if os.path.exists(local_path):
            print(f"[FLOODS] Already have {filename}")
            return [local_path]

        print(f"[FLOODS] Downloading {url} ...")
        try:
            resp = requests.get(url, timeout=120, stream=True, headers={
                'User-Agent': 'Mozilla/5.0 (disaster-data-pipeline)'
            })
            resp.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            print(f"[FLOODS] Saved {local_path} ({os.path.getsize(local_path)} bytes)")
            return [local_path]
        except requests.RequestException as e:
            print(f"[FLOODS] WARNING: Could not download {url}: {e}")

    print("[FLOODS] Could not download DFO archive. Trying HTML scrape...")
    try:
        resp = requests.get(DFO_URL, timeout=60)
        resp.raise_for_status()
        links = re.findall(r'href=["\']([^"\']*\.(xlsx?|csv))["\']', resp.text, re.IGNORECASE)
        for link, _ in links:
            if not link.startswith('http'):
                link = DFO_URL.rsplit('/', 1)[0] + '/' + link
            fname = link.rsplit('/', 1)[-1]
            local = os.path.join(RAW_DIR, fname)
            print(f"[FLOODS] Downloading {link} ...")
            r = requests.get(link, timeout=120, stream=True)
            r.raise_for_status()
            with open(local, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            print(f"[FLOODS] Saved {local}")
            return [local]
    except Exception as e:
        print(f"[FLOODS] WARNING: HTML scrape failed: {e}")

    print("[FLOODS] Download unsuccessful. Place flood data files in raw/floods/ manually.")
    return []


def load(min_year=1976):
    """Load flood data from DFO archive.

    DFO columns typically include:
    - Register #, GlideNumber, Country, OtherCountry
    - Began, Ended (dates)
    - Duration, Dead, Displaced, MainCause, Severity
    - Centroid_X (lon), Centroid_Y (lat), Area (sq km)
    - Validation, Country_code, Long, Lat

    Create polygon features:
    - Use centroid + area to generate approximate polygon (buffer_point with sqrt(area/pi))
    - Set properties: name, type=flooding, year, country, severity, deaths
    """
    excel_files = glob.glob(os.path.join(RAW_DIR, '*.xlsx')) + glob.glob(os.path.join(RAW_DIR, '*.xls'))
    csv_files = glob.glob(os.path.join(RAW_DIR, '*.csv'))

    df = None
    for fpath in excel_files:
        print(f"[FLOODS] Reading Excel file: {fpath}")
        try:
            df = pd.read_excel(fpath, engine='openpyxl')
            print(f"[FLOODS] Loaded {len(df)} rows from {fpath}")
            break
        except Exception as e:
            print(f"[FLOODS] WARNING: Could not read {fpath} with openpyxl: {e}")
            try:
                df = pd.read_excel(fpath)
                print(f"[FLOODS] Loaded {len(df)} rows from {fpath} (fallback engine)")
                break
            except Exception as e2:
                print(f"[FLOODS] WARNING: Could not read {fpath}: {e2}")

    if df is None:
        for fpath in csv_files:
            if 'flood' in fpath.lower() or 'dfo' in fpath.lower() or 'master' in fpath.lower():
                print(f"[FLOODS] Reading CSV file: {fpath}")
                try:
                    df = pd.read_csv(fpath, low_memory=False)
                    print(f"[FLOODS] Loaded {len(df)} rows from {fpath}")
                    break
                except Exception as e:
                    print(f"[FLOODS] WARNING: Could not read {fpath}: {e}")

    if df is None:
        for fpath in csv_files:
            print(f"[FLOODS] Reading CSV file: {fpath}")
            try:
                df = pd.read_csv(fpath, low_memory=False)
                print(f"[FLOODS] Loaded {len(df)} rows from {fpath}")
                break
            except Exception as e:
                print(f"[FLOODS] WARNING: Could not read {fpath}: {e}")

    if df is None:
        print(f"[FLOODS] No data files found in {RAW_DIR}/")
        return load_fallback()

    cols_lower = {c.lower().strip(): c for c in df.columns}

    def _col(names):
        for n in names:
            if n in df.columns:
                return n
            if n.lower() in cols_lower:
                return cols_lower[n.lower()]
        return None

    lat_col = _col(['Centroid_Y', 'centroid_y', 'Lat', 'lat', 'latitude', 'LATITUDE'])
    lon_col = _col(['Centroid_X', 'centroid_x', 'Long', 'lon', 'longitude', 'LONGITUDE'])
    country_col = _col(['Country', 'country', 'COUNTRY'])
    other_country_col = _col(['OtherCountry', 'Other Country', 'other_country'])
    began_col = _col(['Began', 'began', 'Start', 'start_date', 'BEGIN_DATE'])
    ended_col = _col(['Ended', 'ended', 'End', 'end_date', 'END_DATE'])
    dead_col = _col(['Dead', 'dead', 'Deaths', 'deaths', 'DEATHS', 'Total Deaths'])
    displaced_col = _col(['Displaced', 'displaced', 'DISPLACED', 'Total Affected'])
    severity_col = _col(['Severity', 'severity', 'SEVERITY', 'Severity (class)'])
    area_col = _col(['Area', 'area', 'AREA', 'Area (sq km)', 'area_sqkm'])
    cause_col = _col(['MainCause', 'main_cause', 'Cause', 'cause', 'CAUSE'])
    register_col = _col(['Register #', 'Register', 'register', 'ID', 'id'])
    glide_col = _col(['GlideNumber', 'Glide', 'glide_number', 'GLIDE'])
    duration_col = _col(['Duration', 'duration', 'DURATION'])
    validation_col = _col(['Validation', 'validation'])

    features = []
    skipped = 0

    for idx, row in df.iterrows():
        lat = safe_float(row.get(lat_col)) if lat_col else None
        lon = safe_float(row.get(lon_col)) if lon_col else None

        if lat is None or lon is None:
            skipped += 1
            continue

        lat = clamp_lat(lat)
        lon = clamp_lon(lon)

        country_raw = safe_str(row.get(country_col)) if country_col else None
        country = normalize_country(country_raw) if country_raw else None

        other_countries = safe_str(row.get(other_country_col)) if other_country_col else None

        began = None
        year = None
        if began_col:
            began = parse_date(row.get(began_col))
            if began:
                year = int(began[:4])

        if year is None:
            year_val = safe_int(row.get('Year') if 'Year' in df.columns else None)
            if year_val:
                year = year_val

        if year is not None and year < min_year:
            continue

        ended = parse_date(row.get(ended_col)) if ended_col else None
        deaths = safe_int(row.get(dead_col)) if dead_col else None
        displaced = safe_int(row.get(displaced_col)) if displaced_col else None
        severity = safe_float(row.get(severity_col)) if severity_col else None
        area_sqkm = safe_float(row.get(area_col)) if area_col else None
        cause = safe_str(row.get(cause_col)) if cause_col else None
        register = safe_str(row.get(register_col)) if register_col else None
        glide = safe_str(row.get(glide_col)) if glide_col else None
        duration = safe_int(row.get(duration_col)) if duration_col else None

        name_parts = []
        if country:
            name_parts.append(country)
        if year:
            name_parts.append(str(year))
        name_parts.append('Flood')
        if register:
            name_parts.append(f"#{register}")
        name = ' '.join(name_parts)

        props = {
            'name': name,
            'type': 'flooding',
            'year': year,
            'start_date': began,
            'end_date': ended,
            'country': country,
            'other_countries': other_countries,
            'deaths': deaths,
            'displaced': displaced,
            'severity': severity,
            'area_sqkm': area_sqkm,
            'duration_days': duration,
            'cause': cause,
            'register_id': register,
            'glide_number': glide,
            'source': 'Dartmouth Flood Observatory',
        }
        props = {k: v for k, v in props.items() if v is not None}

        if area_sqkm and area_sqkm > 0:
            radius_km = math.sqrt(area_sqkm / math.pi)
            radius_km = max(10, min(radius_km, 1000))
            coords = buffer_point(lon, lat, radius_km)
            feat = polygon_feature(coords, props)
        elif severity and severity >= 1.5:
            radius_km = 50 + (severity - 1) * 50
            coords = buffer_point(lon, lat, radius_km)
            feat = polygon_feature(coords, props)
        else:
            feat = point_feature(lon, lat, props)

        features.append(feat)

    print(f"[FLOODS] Generated {len(features)} flood features ({skipped} skipped, no coords).")
    return features


def load_fallback():
    """Load any CSV/GeoJSON flood data from raw/floods/."""
    features = []
    for pattern in ['*.geojson', '*.json']:
        for fpath in glob.glob(os.path.join(RAW_DIR, pattern)):
            print(f"[FLOODS] Loading fallback: {fpath}")
            try:
                with open(fpath) as f:
                    data = json.load(f)
                if data.get('type') == 'FeatureCollection':
                    for feat in data.get('features', []):
                        feat.setdefault('properties', {})['source'] = 'DFO (fallback)'
                        features.append(feat)
                elif data.get('type') == 'Feature':
                    data.setdefault('properties', {})['source'] = 'DFO (fallback)'
                    features.append(data)
            except Exception as e:
                print(f"[FLOODS] WARNING: Could not read {fpath}: {e}")

    for fpath in glob.glob(os.path.join(RAW_DIR, '*.csv')):
        print(f"[FLOODS] Loading fallback CSV: {fpath}")
        try:
            df = pd.read_csv(fpath, low_memory=False)
            cols_lower = {c.lower(): c for c in df.columns}
            lat_col = None
            lon_col = None
            for name in ['latitude', 'lat', 'centroid_y']:
                if name in cols_lower:
                    lat_col = cols_lower[name]
                    break
            for name in ['longitude', 'lon', 'long', 'centroid_x']:
                if name in cols_lower:
                    lon_col = cols_lower[name]
                    break
            if lat_col and lon_col:
                for _, row in df.iterrows():
                    lat = safe_float(row.get(lat_col))
                    lon = safe_float(row.get(lon_col))
                    if lat is not None and lon is not None:
                        props = {k: safe_str(v) for k, v in row.to_dict().items() if safe_str(v) is not None}
                        props['type'] = 'flooding'
                        props['source'] = 'DFO (fallback CSV)'
                        features.append(point_feature(lon, lat, props))
        except Exception as e:
            print(f"[FLOODS] WARNING: Could not read {fpath}: {e}")

    print(f"[FLOODS] Fallback loaded {len(features)} features.")
    return features


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Flood data importer (DFO)')
    parser.add_argument('--download', action='store_true', help='Download data')
    parser.add_argument('--min-year', type=int, default=1976)
    args = parser.parse_args()

    if args.download:
        download()

    features = load(min_year=args.min_year)
    print(f"Total flood features: {len(features)}")
    if features:
        countries = {}
        for f in features:
            c = f['properties'].get('country', 'Unknown')
            countries[c] = countries.get(c, 0) + 1
        for c, n in sorted(countries.items(), key=lambda x: -x[1])[:20]:
            print(f"  {c}: {n}")
