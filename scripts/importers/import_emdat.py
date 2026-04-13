"""
EM-DAT (Emergency Events Database) importer.
EM-DAT requires registration for download, so this importer:
1. Reads pre-downloaded EM-DAT Excel/CSV exports from raw/emdat/
2. Falls back to curated data if no export available
EM-DAT provides: disaster type, country, year, deaths, affected, damage, start/end dates.
"""

import os
import sys
import glob
import json
import math

import pandas as pd

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

RAW_DIR = 'raw/emdat'

EMDAT_TYPE_MAP = {
    'Earthquake': 'earthquake',
    'Storm': 'hurricane',
    'Flood': 'flooding',
    'Drought': 'drought',
    'Wildfire': 'wildfire',
    'Volcanic activity': 'volcanic_eruption',
    'Extreme temperature': None,
    'Mass movement (wet)': 'flooding',
    'Mass movement (dry)': 'earthquake',
    'Epidemic': 'epidemic',
    'Insect infestation': None,
    'Animal accident': None,
    'Fog': None,
    'Glacial lake outburst': 'flooding',
}

STORM_SUBTYPE_MAP = {
    'Tropical cyclone': 'hurricane',
    'Extra-tropical storm': 'hurricane',
    'Convective storm': 'tornado',
    'Tornado': 'tornado',
    'Derecho': 'tornado',
    'Hail': 'tornado',
    'Lightning/Thunderstorms': 'tornado',
    'Winter storm/Blizzard': 'blizzard',
    'Snow/Ice': 'blizzard',
    'Storm surge': 'hurricane',
}

TEMP_SUBTYPE_MAP = {
    'Heat wave': 'heat_wave',
    'Cold wave': 'cold_wave',
    'Severe winter conditions': 'cold_wave',
    'Dzud': 'cold_wave',
}


def download():
    """EM-DAT requires registration. Print instructions for manual download."""
    os.makedirs(RAW_DIR, exist_ok=True)
    print("=" * 60)
    print("EM-DAT requires free registration at https://public.emdat.be/")
    print("Steps:")
    print("  1. Register/login at https://public.emdat.be/")
    print("  2. Go to 'Data' section")
    print("  3. Select all disaster types and desired date range")
    print("  4. Export as Excel (.xlsx)")
    print("  5. Place the downloaded file in raw/emdat/")
    print("=" * 60)

    existing = glob.glob(os.path.join(RAW_DIR, '*.xlsx')) + glob.glob(os.path.join(RAW_DIR, '*.csv'))
    if existing:
        print(f"[EM-DAT] Found {len(existing)} existing data files:")
        for f in existing:
            print(f"  {f}")
    else:
        print(f"[EM-DAT] No data files found in {RAW_DIR}/")

    return existing


def map_emdat_type(disaster_type, disaster_subtype):
    """Map EM-DAT disaster type + subtype to our canonical type."""
    if not disaster_type:
        return None

    disaster_type = str(disaster_type).strip()
    disaster_subtype = str(disaster_subtype).strip() if disaster_subtype else ''

    if disaster_type == 'Storm':
        for key, val in STORM_SUBTYPE_MAP.items():
            if key.lower() in disaster_subtype.lower():
                return val
        return 'hurricane'

    if disaster_type == 'Extreme temperature':
        for key, val in TEMP_SUBTYPE_MAP.items():
            if key.lower() in disaster_subtype.lower():
                return val
        if 'heat' in disaster_subtype.lower() or 'hot' in disaster_subtype.lower():
            return 'heat_wave'
        if 'cold' in disaster_subtype.lower() or 'winter' in disaster_subtype.lower() or 'frost' in disaster_subtype.lower():
            return 'cold_wave'
        return None

    return EMDAT_TYPE_MAP.get(disaster_type)


def load(min_year=1976):
    """Load EM-DAT data from Excel/CSV exports.

    EM-DAT columns: Dis No, Year, Seq, Disaster Group, Disaster Subgroup,
    Disaster Type, Disaster Subtype, Event Name, Country, ISO, Region,
    Continent, Location, Origin, Associated Dis, Associated Dis2,
    Start Year, Start Month, Start Day, End Year, End Month, End Day,
    Total Deaths, No Injured, No Affected, No Homeless, Total Affected,
    Reconstruction Costs, Insured Damages, Total Damages, CPI,
    Latitude, Longitude

    Map disaster types to our canonical types.
    Create features with Point geometry (lat/lon if available).
    Rich impact data: deaths, affected, damages.
    """
    excel_files = sorted(glob.glob(os.path.join(RAW_DIR, '*.xlsx')) + glob.glob(os.path.join(RAW_DIR, '*.xls')))
    csv_files = sorted(glob.glob(os.path.join(RAW_DIR, '*.csv')))

    df = None
    for fpath in excel_files:
        print(f"[EM-DAT] Reading Excel file: {fpath}")
        try:
            df = pd.read_excel(fpath, engine='openpyxl')
            print(f"[EM-DAT] Loaded {len(df)} rows from {fpath}")
            break
        except Exception as e:
            print(f"[EM-DAT] WARNING: Could not read {fpath} with openpyxl: {e}")
            try:
                df = pd.read_excel(fpath)
                print(f"[EM-DAT] Loaded {len(df)} rows from {fpath} (fallback engine)")
                break
            except Exception as e2:
                print(f"[EM-DAT] WARNING: Could not read {fpath}: {e2}")

    if df is None:
        for fpath in csv_files:
            print(f"[EM-DAT] Reading CSV file: {fpath}")
            try:
                df = pd.read_csv(fpath, low_memory=False, encoding='utf-8')
                print(f"[EM-DAT] Loaded {len(df)} rows from {fpath}")
                break
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(fpath, low_memory=False, encoding='latin-1')
                    print(f"[EM-DAT] Loaded {len(df)} rows from {fpath} (latin-1)")
                    break
                except Exception as e:
                    print(f"[EM-DAT] WARNING: Could not read {fpath}: {e}")
            except Exception as e:
                print(f"[EM-DAT] WARNING: Could not read {fpath}: {e}")

    if df is None:
        print(f"[EM-DAT] No data files found in {RAW_DIR}/")
        return _load_fallback_geojson()

    return _process_dataframe(df, min_year)


def _process_dataframe(df, min_year):
    """Process an EM-DAT dataframe into GeoJSON features."""
    cols_lower = {c.lower().strip().replace("'", "").replace('"', ''): c for c in df.columns}

    def _col(names):
        for n in names:
            if n in df.columns:
                return n
            nl = n.lower().strip()
            if nl in cols_lower:
                return cols_lower[nl]
        return None

    dis_no_col = _col(['Dis No', 'DisNo', 'dis_no', 'Disaster No', 'disaster_no'])
    year_col = _col(['Year', 'year', 'Start Year', 'start_year'])
    type_col = _col(['Disaster Type', 'disaster_type', 'Type', 'type'])
    subtype_col = _col(['Disaster Subtype', 'disaster_subtype', 'Subtype', 'subtype'])
    name_col = _col(['Event Name', 'event_name', 'Name', 'name', 'Event'])
    country_col = _col(['Country', 'country', 'COUNTRY'])
    iso_col = _col(['ISO', 'iso', 'Country code', 'country_code'])
    region_col = _col(['Region', 'region'])
    continent_col = _col(['Continent', 'continent'])
    location_col = _col(['Location', 'location'])
    lat_col = _col(['Latitude', 'latitude', 'lat', 'Lat'])
    lon_col = _col(['Longitude', 'longitude', 'lon', 'Lon', 'Long'])
    deaths_col = _col(['Total Deaths', 'total_deaths', 'Deaths', 'deaths', 'No. Deaths', 'Killed'])
    injured_col = _col(['No Injured', 'no_injured', 'Injured', 'injured', 'No. Injured'])
    affected_col = _col(['Total Affected', 'total_affected', 'Affected', 'affected', 'No. Affected', 'Total_Affected'])
    homeless_col = _col(['No Homeless', 'no_homeless', 'Homeless', 'homeless'])
    damage_col = _col(["Total Damages ('000 US$)", 'Total Damages', 'total_damages', 'Damages', "Total Damages, Adjusted ('000 US$)", 'Reconstruction Costs'])
    insured_col = _col(["Insured Damages ('000 US$)", 'Insured Damages', 'insured_damages'])
    start_month_col = _col(['Start Month', 'start_month'])
    start_day_col = _col(['Start Day', 'start_day'])
    end_year_col = _col(['End Year', 'end_year'])
    end_month_col = _col(['End Month', 'end_month'])
    end_day_col = _col(['End Day', 'end_day'])
    origin_col = _col(['Origin', 'origin'])
    group_col = _col(['Disaster Group', 'disaster_group'])
    subgroup_col = _col(['Disaster Subgroup', 'disaster_subgroup'])

    features = []
    skipped_type = 0
    skipped_year = 0

    print(f"[EM-DAT] Processing {len(df)} rows...")

    for idx, row in df.iterrows():
        disaster_type = clean_string(row.get(type_col)) if type_col else None
        disaster_subtype = clean_string(row.get(subtype_col)) if subtype_col else None

        our_type = map_emdat_type(disaster_type, disaster_subtype)
        if our_type is None:
            skipped_type += 1
            continue

        year = parse_int(row.get(year_col)) if year_col else None
        if year is None:
            continue
        if year < min_year:
            skipped_year += 1
            continue

        lat = parse_float(row.get(lat_col)) if lat_col else None
        lon = parse_float(row.get(lon_col)) if lon_col else None

        country_raw = clean_string(row.get(country_col)) if country_col else None
        country = normalize_country(country_raw) if country_raw else None
        iso = clean_string(row.get(iso_col)) if iso_col else None

        event_name = clean_string(row.get(name_col)) if name_col else None
        dis_no = clean_string(row.get(dis_no_col)) if dis_no_col else None
        region = clean_string(row.get(region_col)) if region_col else None
        continent = clean_string(row.get(continent_col)) if continent_col else None
        location = clean_string(row.get(location_col)) if location_col else None

        deaths = parse_int(row.get(deaths_col)) if deaths_col else None
        injured = parse_int(row.get(injured_col)) if injured_col else None
        affected = parse_int(row.get(affected_col)) if affected_col else None
        homeless = parse_int(row.get(homeless_col)) if homeless_col else None

        damage_thousands = parse_float(row.get(damage_col)) if damage_col else None
        damage_usd = damage_thousands * 1000 if damage_thousands else None
        insured_thousands = parse_float(row.get(insured_col)) if insured_col else None
        insured_usd = insured_thousands * 1000 if insured_thousands else None

        start_month = parse_int(row.get(start_month_col)) if start_month_col else None
        start_day = parse_int(row.get(start_day_col)) if start_day_col else None
        end_yr = parse_int(row.get(end_year_col)) if end_year_col else None
        end_mo = parse_int(row.get(end_month_col)) if end_month_col else None
        end_dy = parse_int(row.get(end_day_col)) if end_day_col else None

        start_date = _build_date(year, start_month, start_day)
        end_date = _build_date(end_yr or year, end_mo or start_month, end_dy)

        if event_name:
            name = event_name
        else:
            name_parts = []
            if country:
                name_parts.append(country)
            name_parts.append(str(year))
            name_parts.append(our_type.replace('_', ' ').title())
            name = ' '.join(name_parts)

        props = {
            'name': name,
            'type': our_type,
            'year': year,
            'start_date': start_date,
            'end_date': end_date,
            'country': country,
            'iso_code': iso,
            'region': region,
            'continent': continent,
            'location': location,
            'deaths': deaths,
            'injured': injured,
            'affected': affected,
            'homeless': homeless,
            'damage_usd': damage_usd,
            'insured_damage_usd': insured_usd,
            'disaster_type_original': disaster_type,
            'disaster_subtype_original': disaster_subtype,
            'dis_no': dis_no,
            'source': 'EM-DAT',
        }
        props = {k: v for k, v in props.items() if v is not None}

        if lat is not None and lon is not None:
            lat = _clamp_lat(lat)
            lon = _clamp_lon(lon)
            feat = point_feature(lon, lat, props)
        elif country:
            coords = _country_centroid(country)
            if coords:
                feat = point_feature(coords[0], coords[1], props)
            else:
                continue
        else:
            continue

        features.append(feat)

    print(f"[EM-DAT] Generated {len(features)} features ({skipped_type} skipped by type, {skipped_year} skipped by year).")

    if features:
        type_counts = {}
        for f in features:
            t = f['properties'].get('type', 'unknown')
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"[EM-DAT]   {t}: {c}")

    return features


def _build_date(year, month, day):
    """Build a date string from year/month/day, handling missing parts."""
    if year is None:
        return None
    y = int(year)
    m = int(month) if month else 1
    d = int(day) if day else 1
    m = max(1, min(12, m))
    d = max(1, min(28, d))
    return f"{y:04d}-{m:02d}-{d:02d}"


COUNTRY_CENTROIDS = {
    'United States': (-98.5, 39.8),
    'China': (104.2, 35.9),
    'India': (78.9, 20.6),
    'Indonesia': (113.9, -0.8),
    'Brazil': (-51.9, -14.2),
    'Russia': (105.3, 61.5),
    'Mexico': (-102.6, 23.6),
    'Japan': (138.3, 36.2),
    'Philippines': (122.0, 12.9),
    'Turkey': (35.2, 38.9),
    'Iran': (53.7, 32.4),
    'Pakistan': (69.3, 30.4),
    'Bangladesh': (90.4, 23.7),
    'Colombia': (-74.3, 4.6),
    'Peru': (-75.0, -9.2),
    'Chile': (-71.5, -35.7),
    'Italy': (12.6, 41.9),
    'France': (2.2, 46.2),
    'Germany': (10.5, 51.2),
    'United Kingdom': (-3.4, 55.4),
    'Spain': (-3.7, 40.5),
    'Australia': (133.8, -25.3),
    'Canada': (-106.3, 56.1),
    'Argentina': (-63.6, -38.4),
    'South Africa': (22.9, -30.6),
    'Nigeria': (8.7, 9.1),
    'Ethiopia': (40.5, 9.1),
    'Kenya': (37.9, -0.0),
    'Egypt': (30.8, 26.8),
    'DR Congo': (21.8, -4.0),
    'Afghanistan': (67.7, 33.9),
    'Myanmar': (96.0, 21.9),
    'Thailand': (100.5, 15.9),
    'Vietnam': (108.3, 14.1),
    'South Korea': (127.8, 35.9),
    'North Korea': (127.5, 40.3),
    'Nepal': (84.1, 28.4),
    'Sri Lanka': (80.8, 7.9),
    'Haiti': (-72.3, 19.0),
    'Cuba': (-77.8, 21.5),
    'Guatemala': (-90.2, 15.8),
    'Honduras': (-86.2, 15.2),
    'New Zealand': (174.9, -40.9),
    'Greece': (21.8, 39.1),
    'Portugal': (-8.2, 39.4),
    'Romania': (24.9, 45.9),
    'Poland': (19.1, 51.9),
    'Ukraine': (31.2, 48.4),
    'Morocco': (-7.1, 31.8),
    'Algeria': (1.7, 28.0),
    'Mozambique': (35.5, -18.7),
    'Tanzania': (34.9, -6.4),
    'Madagascar': (46.9, -18.8),
    'Somalia': (46.2, 5.2),
    'Sudan': (30.2, 12.9),
    'Mali': (-1.2, 17.6),
    'Niger': (8.1, 17.6),
    'Chad': (18.7, 15.5),
    'Senegal': (-14.5, 14.5),
    'Mongolia': (103.8, 46.9),
}


def _country_centroid(country):
    """Get approximate centroid [lon, lat] for a country name."""
    if not country:
        return None
    normalized = normalize_country(country)
    return COUNTRY_CENTROIDS.get(normalized) or COUNTRY_CENTROIDS.get(country)


def _load_fallback_geojson():
    """Load any GeoJSON or CSV files from the raw directory as fallback."""
    features = []

    for fpath in glob.glob(os.path.join(RAW_DIR, '*.geojson')) + glob.glob(os.path.join(RAW_DIR, '*.json')):
        print(f"[EM-DAT] Loading fallback: {fpath}")
        try:
            with open(fpath) as f:
                data = json.load(f)
            if data.get('type') == 'FeatureCollection':
                for feat in data.get('features', []):
                    feat.setdefault('properties', {})['source'] = 'EM-DAT (fallback)'
                    features.append(feat)
            elif data.get('type') == 'Feature':
                data.setdefault('properties', {})['source'] = 'EM-DAT (fallback)'
                features.append(data)
        except Exception as e:
            print(f"[EM-DAT] WARNING: Could not read {fpath}: {e}")

    for fpath in glob.glob(os.path.join(RAW_DIR, '*.csv')):
        print(f"[EM-DAT] Loading fallback CSV: {fpath}")
        try:
            df = pd.read_csv(fpath, low_memory=False)
            loaded = _process_dataframe(df, min_year=0)
            features.extend(loaded)
        except Exception as e:
            print(f"[EM-DAT] WARNING: Could not read {fpath}: {e}")

    print(f"[EM-DAT] Fallback loaded {len(features)} features.")
    return features


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='EM-DAT disaster database importer')
    parser.add_argument('--download', action='store_true', help='Show download instructions')
    parser.add_argument('--min-year', type=int, default=1976)
    args = parser.parse_args()

    if args.download:
        download()

    features = load(min_year=args.min_year)
    print(f"Total EM-DAT features: {len(features)}")
    if features:
        by_type = {}
        for f in features:
            t = f['properties'].get('type', 'unknown')
            by_type[t] = by_type.get(t, 0) + 1
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        by_country = {}
        for f in features:
            c = f['properties'].get('country', 'Unknown')
            by_country[c] = by_country.get(c, 0) + 1
        print(f"Top countries:")
        for c, n in sorted(by_country.items(), key=lambda x: -x[1])[:15]:
            print(f"  {c}: {n}")
