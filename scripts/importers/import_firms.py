"""
NASA FIRMS (Fire Information for Resource Management System) importer.
Active fire data from MODIS and VIIRS satellites.
Download: https://firms.modaps.eosdis.nasa.gov/data/active_fire/
Note: Historical archive requires FIRMS key or bulk download.
Alternative: Use aggregated fire datasets or MTBS for US.
"""

import os
import sys
import re
import glob
import math
import json
from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.normalize import *
from scripts.utils.geo import *

RAW_DIR = 'raw/firms'

FIRMS_API_BASE = 'https://firms.modaps.eosdis.nasa.gov'


def download(min_year=2000):
    """Download available FIRMS data.
    Note: Full historical archive requires authentication.
    For the pipeline, support reading pre-downloaded CSVs.
    Also download MTBS perimeter data for US if available.
    """
    os.makedirs(RAW_DIR, exist_ok=True)

    firms_key = os.environ.get('FIRMS_MAP_KEY', '')
    if firms_key:
        print("[FIRMS] FIRMS_MAP_KEY found, attempting API download...")
        for source in ['MODIS_NRT', 'VIIRS_NOAA20_NRT']:
            url = f"{FIRMS_API_BASE}/api/area/csv/{firms_key}/{source}/world/10"
            print(f"[FIRMS] Downloading recent {source} data...")
            try:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                out_path = os.path.join(RAW_DIR, f'{source}_recent.csv')
                with open(out_path, 'w') as f:
                    f.write(resp.text)
                print(f"[FIRMS] Saved {out_path} ({len(resp.text)} bytes)")
            except requests.RequestException as e:
                print(f"[FIRMS] WARNING: Could not download {source}: {e}")
    else:
        print("[FIRMS] No FIRMS_MAP_KEY set. To download data:")
        print("  1. Register at https://firms.modaps.eosdis.nasa.gov/")
        print("  2. Set FIRMS_MAP_KEY environment variable")
        print("  3. Or place pre-downloaded CSV files in raw/firms/")

    mtbs_url = 'https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/MTBS_Fire/data/composite_data/burned_area_extent_shapefile/mtbs_perimeter_data.zip'
    mtbs_path = os.path.join(RAW_DIR, 'mtbs_perimeter_data.zip')
    if not os.path.exists(mtbs_path):
        print("[FIRMS] Attempting MTBS perimeter data download...")
        try:
            resp = requests.get(mtbs_url, timeout=300, stream=True)
            resp.raise_for_status()
            with open(mtbs_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            print(f"[FIRMS] Saved MTBS data to {mtbs_path}")
        except requests.RequestException as e:
            print(f"[FIRMS] WARNING: Could not download MTBS data: {e}")

    existing = glob.glob(os.path.join(RAW_DIR, '*.csv'))
    print(f"[FIRMS] {len(existing)} CSV files available in {RAW_DIR}/")
    return existing


def cluster_fires(detections, distance_km=50, time_days=7):
    """Simple spatial-temporal clustering of fire detections.

    Uses a greedy approach: iterate sorted detections, assign each to the
    nearest existing cluster within thresholds, or start a new cluster.
    """
    if not detections:
        return []

    detections_sorted = sorted(detections, key=lambda d: d['date'])

    clusters = []
    for det in detections_sorted:
        best_cluster = None
        best_dist = float('inf')

        for cluster in clusters:
            last_date = cluster['last_date']
            dt = (det['date'] - last_date).days
            if dt > time_days:
                continue

            dlat = det['lat'] - cluster['center_lat']
            dlon = det['lon'] - cluster['center_lon']
            dist = math.sqrt(dlat ** 2 + dlon ** 2) * 111.0
            if dist < distance_km and dist < best_dist:
                best_dist = dist
                best_cluster = cluster

        if best_cluster is not None:
            best_cluster['points'].append(det)
            best_cluster['last_date'] = max(best_cluster['last_date'], det['date'])
            n = len(best_cluster['points'])
            best_cluster['center_lat'] = (best_cluster['center_lat'] * (n - 1) + det['lat']) / n
            best_cluster['center_lon'] = (best_cluster['center_lon'] * (n - 1) + det['lon']) / n
        else:
            clusters.append({
                'center_lat': det['lat'],
                'center_lon': det['lon'],
                'first_date': det['date'],
                'last_date': det['date'],
                'points': [det],
            })

    return clusters


def load(min_year=2000, min_frp=100):
    """Load FIRMS CSV data, cluster fire detections into discrete fire events.

    Processing:
    - Read all CSV files from raw/firms/
    - Filter by confidence and FRP (fire radiative power)
    - Cluster nearby detections (within ~50km and ~7 days) into events
    - For each cluster: create Point at centroid, calculate total FRP
    - Generate approximate burn polygon from convex hull of cluster
    - Set properties: name (from country+year+size rank), type=wildfire
    - Return list of features
    """
    csv_files = sorted(glob.glob(os.path.join(RAW_DIR, '*.csv')))
    if not csv_files:
        print(f"[FIRMS] No CSV files found in {RAW_DIR}/")
        return load_fallback()

    all_detections = []
    print(f"[FIRMS] Reading {len(csv_files)} CSV files...")
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath, low_memory=False)
        except Exception as e:
            print(f"[FIRMS] WARNING: Could not read {filepath}: {e}")
            continue

        lat_col = _find_col(df, ['latitude', 'lat', 'LATITUDE'])
        lon_col = _find_col(df, ['longitude', 'lon', 'LONGITUDE'])
        date_col = _find_col(df, ['acq_date', 'ACQ_DATE', 'date', 'DATE'])
        frp_col = _find_col(df, ['frp', 'FRP', 'fire_radiative_power'])
        conf_col = _find_col(df, ['confidence', 'CONFIDENCE', 'conf'])
        bright_col = _find_col(df, ['brightness', 'BRIGHTNESS', 'bright_ti4'])

        if not lat_col or not lon_col:
            print(f"[FIRMS] WARNING: {filepath} missing lat/lon columns, skipping.")
            continue

        for _, row in df.iterrows():
            lat = safe_float(row.get(lat_col))
            lon = safe_float(row.get(lon_col))
            if lat is None or lon is None:
                continue

            frp = safe_float(row.get(frp_col)) if frp_col else None
            if frp is not None and frp < min_frp:
                continue

            if conf_col:
                conf = safe_str(row.get(conf_col), '')
                if conf.lower() in ('l', 'low', '0'):
                    continue

            acq_date = None
            if date_col:
                raw_date = safe_str(row.get(date_col))
                if raw_date:
                    parsed = parse_date(raw_date)
                    if parsed:
                        try:
                            acq_date = datetime.strptime(parsed, '%Y-%m-%d')
                        except ValueError:
                            pass

            if acq_date is None:
                continue
            if acq_date.year < min_year:
                continue

            brightness = safe_float(row.get(bright_col)) if bright_col else None

            all_detections.append({
                'lat': clamp_lat(lat),
                'lon': clamp_lon(lon),
                'date': acq_date,
                'frp': frp or 0,
                'brightness': brightness or 0,
            })

    if not all_detections:
        print("[FIRMS] No valid fire detections found after filtering.")
        return load_fallback()

    print(f"[FIRMS] {len(all_detections)} detections passed filters. Clustering...")
    clusters = cluster_fires(all_detections, distance_km=50, time_days=7)
    print(f"[FIRMS] Found {len(clusters)} fire clusters.")

    min_cluster_size = 3
    significant = [c for c in clusters if len(c['points']) >= min_cluster_size]
    significant.sort(key=lambda c: sum(p['frp'] for p in c['points']), reverse=True)
    print(f"[FIRMS] {len(significant)} clusters with >= {min_cluster_size} detections.")

    features = []
    for rank, cluster in enumerate(significant, 1):
        points = cluster['points']
        total_frp = sum(p['frp'] for p in points)
        max_frp = max(p['frp'] for p in points)
        center_lat = cluster['center_lat']
        center_lon = cluster['center_lon']
        first_date = cluster['first_date']
        last_date = cluster['last_date']
        duration_days = max(1, (last_date - first_date).days)
        year = first_date.year

        lats = [p['lat'] for p in points]
        lons = [p['lon'] for p in points]
        spread_km = math.sqrt((max(lats) - min(lats)) ** 2 + (max(lons) - min(lons)) ** 2) * 111

        name = f"Fire {year}-{rank:04d} ({first_date.strftime('%b')})"

        props = {
            'name': name,
            'type': 'wildfire',
            'year': year,
            'start_date': first_date.strftime('%Y-%m-%d'),
            'end_date': last_date.strftime('%Y-%m-%d'),
            'duration_days': duration_days,
            'detection_count': len(points),
            'total_frp': round(total_frp, 1),
            'max_frp': round(max_frp, 1),
            'spread_km': round(spread_km, 1),
            'source': 'NASA FIRMS',
        }

        if len(points) >= 4:
            try:
                from shapely.geometry import MultiPoint as _MP
                mp = _MP([(p['lon'], p['lat']) for p in points])
                hull = mp.convex_hull
                if hull.geom_type == 'Polygon':
                    coords = list(hull.exterior.coords)
                    feat = polygon_feature(coords, props)
                else:
                    radius_km = max(5, spread_km / 2)
                    coords = buffer_point(center_lon, center_lat, radius_km)
                    feat = polygon_feature(coords, props)
            except Exception:
                radius_km = max(5, spread_km / 2)
                coords = buffer_point(center_lon, center_lat, radius_km)
                feat = polygon_feature(coords, props)
        elif spread_km > 1:
            radius_km = max(5, spread_km / 2)
            coords = buffer_point(center_lon, center_lat, radius_km)
            feat = polygon_feature(coords, props)
        else:
            feat = point_feature(center_lon, center_lat, props)

        features.append(feat)

    print(f"[FIRMS] Generated {len(features)} wildfire features.")
    return features


def load_fallback():
    """If no FIRMS data available, load from any CSV/GeoJSON in raw/firms/."""
    features = []
    for pattern in ['*.geojson', '*.json']:
        for fpath in glob.glob(os.path.join(RAW_DIR, pattern)):
            print(f"[FIRMS] Loading fallback file: {fpath}")
            try:
                with open(fpath) as f:
                    data = json.load(f)
                if data.get('type') == 'FeatureCollection':
                    for feat in data.get('features', []):
                        feat.setdefault('properties', {})['source'] = 'FIRMS (fallback)'
                        features.append(feat)
                elif data.get('type') == 'Feature':
                    data.setdefault('properties', {})['source'] = 'FIRMS (fallback)'
                    features.append(data)
            except Exception as e:
                print(f"[FIRMS] WARNING: Could not read {fpath}: {e}")

    for fpath in glob.glob(os.path.join(RAW_DIR, '*.csv')):
        print(f"[FIRMS] Loading fallback CSV: {fpath}")
        try:
            df = pd.read_csv(fpath, low_memory=False)
            lat_col = _find_col(df, ['latitude', 'lat', 'LATITUDE'])
            lon_col = _find_col(df, ['longitude', 'lon', 'LONGITUDE'])
            if lat_col and lon_col:
                for _, row in df.iterrows():
                    lat = safe_float(row.get(lat_col))
                    lon = safe_float(row.get(lon_col))
                    if lat is not None and lon is not None:
                        props = {}
                        for col in df.columns:
                            val = safe_str(row.get(col))
                            if val is not None:
                                props[col] = val
                        props['type'] = 'wildfire'
                        props['source'] = 'FIRMS (fallback CSV)'
                        features.append(point_feature(lon, lat, props))
        except Exception as e:
            print(f"[FIRMS] WARNING: Could not read {fpath}: {e}")

    print(f"[FIRMS] Fallback loaded {len(features)} features.")
    return features


def _find_col(df, candidates):
    """Find the first matching column name from a list of candidates."""
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='NASA FIRMS wildfire data importer')
    parser.add_argument('--download', action='store_true', help='Download data files')
    parser.add_argument('--min-year', type=int, default=2000)
    parser.add_argument('--min-frp', type=float, default=100)
    args = parser.parse_args()

    if args.download:
        download(min_year=args.min_year)

    features = load(min_year=args.min_year, min_frp=args.min_frp)
    print(f"Total wildfire features: {len(features)}")
    if features:
        years = defaultdict(int)
        for f in features:
            years[f['properties'].get('year', 'unknown')] += 1
        for y, c in sorted(years.items()):
            print(f"  {y}: {c}")
