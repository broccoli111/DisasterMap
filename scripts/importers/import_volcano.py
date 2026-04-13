"""
Smithsonian Global Volcanism Program (GVP) eruption database importer.
Downloads/reads volcanic eruption records and volcano location data.

Volcano locations (WFS GeoJSON):
    https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes&outputFormat=application/json

Usage:
    python import_volcano.py --download       # download data from GVP
    python import_volcano.py                  # load & parse cached files
    python import_volcano.py --min-year 2000  # load with year filter
"""

import os
import sys
import glob
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.normalize import *
from scripts.utils.geo import *

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'raw', 'volcano')
VOLCANOES_URL = (
    'https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows'
    '?service=WFS&version=1.0.0&request=GetFeature'
    '&typeName=GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes'
    '&outputFormat=application/json'
)

VOLCANO_TYPE_MAP = {
    'Stratovolcano': 'Stratovolcano',
    'Stratovolcano(es)': 'Stratovolcano',
    'Shield': 'Shield volcano',
    'Shield(s)': 'Shield volcano',
    'Caldera': 'Caldera',
    'Complex': 'Complex volcano',
    'Submarine': 'Submarine volcano',
    'Lava dome': 'Lava dome',
    'Lava dome(s)': 'Lava dome',
    'Pyroclastic cone': 'Pyroclastic cone',
    'Pyroclastic cone(s)': 'Pyroclastic cone',
    'Volcanic field': 'Volcanic field',
    'Fissure vent': 'Fissure vent',
    'Fissure vent(s)': 'Fissure vent',
    'Maar': 'Maar',
    'Maar(s)': 'Maar',
    'Tuff cone': 'Tuff cone',
    'Tuff cone(s)': 'Tuff cone',
    'Tuff ring': 'Tuff ring',
    'Tuff ring(s)': 'Tuff ring',
}

VEI_DESCRIPTIONS = {
    0: 'Non-explosive',
    1: 'Gentle',
    2: 'Explosive',
    3: 'Severe',
    4: 'Cataclysmic',
    5: 'Paroxysmal',
    6: 'Colossal',
    7: 'Super-colossal',
    8: 'Mega-colossal',
}


def download():
    """Download volcano locations GeoJSON and eruption data from Smithsonian GVP."""
    import requests

    os.makedirs(RAW_DIR, exist_ok=True)

    volcanoes_path = os.path.join(RAW_DIR, 'gvp_holocene_volcanoes.json')
    if os.path.exists(volcanoes_path):
        size_kb = os.path.getsize(volcanoes_path) / 1024
        print(f"[Volcano] Volcanoes file already exists: {volcanoes_path} ({size_kb:.0f} KB)")
    else:
        print("[Volcano] Downloading Holocene volcano locations from Smithsonian GVP...")
        try:
            resp = requests.get(VOLCANOES_URL, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            with open(volcanoes_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            n = len(data.get('features', []))
            print(f"[Volcano] Saved {n} volcano records to {volcanoes_path}")
        except requests.RequestException as e:
            print(f"[Volcano] Download FAILED: {e}")
        except json.JSONDecodeError as e:
            print(f"[Volcano] Response was not valid JSON: {e}")

    eruptions_path = os.path.join(RAW_DIR, 'gvp_eruptions.json')
    eruptions_url = (
        'https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows'
        '?service=WFS&version=1.0.0&request=GetFeature'
        '&typeName=GVP-VOTW:Smithsonian_VOTW_Holocene_Eruptions'
        '&outputFormat=application/json'
    )
    if os.path.exists(eruptions_path):
        size_kb = os.path.getsize(eruptions_path) / 1024
        print(f"[Volcano] Eruptions file already exists: {eruptions_path} ({size_kb:.0f} KB)")
    else:
        print("[Volcano] Downloading Holocene eruption records...")
        try:
            resp = requests.get(eruptions_url, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            with open(eruptions_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            n = len(data.get('features', []))
            print(f"[Volcano] Saved {n} eruption records to {eruptions_path}")
        except requests.RequestException as e:
            print(f"[Volcano] Eruptions download FAILED (endpoint may not exist): {e}")
            print("  Will fall back to volcano locations with last-eruption-year data.")
        except json.JSONDecodeError as e:
            print(f"[Volcano] Eruptions response was not valid JSON: {e}")

    print("[Volcano] Download complete.")


def parse_volcanoes_geojson(filepath):
    """Parse the Smithsonian GeoJSON response into a list of volcano dicts.
    Each dict has: volcano_number, name, lat, lon, country, region, elevation,
    volcano_type, last_eruption_year.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    volcanoes = []
    for feat in data.get('features', []):
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})

        coords = geom.get('coordinates', [None, None]) if geom else [None, None]
        lon = parse_float(coords[0]) if len(coords) > 0 else None
        lat = parse_float(coords[1]) if len(coords) > 1 else None

        if lon is None or lat is None:
            lat_prop = parse_float(props.get('Latitude') or props.get('latitude'))
            lon_prop = parse_float(props.get('Longitude') or props.get('longitude'))
            if lat_prop is not None and lon_prop is not None:
                lat, lon = lat_prop, lon_prop

        if lat is None or lon is None:
            continue

        name = (
            clean_string(props.get('Volcano_Name'))
            or clean_string(props.get('VolcanoName'))
            or clean_string(props.get('volcano_name'))
            or 'Unknown'
        )

        country = normalize_country(
            clean_string(props.get('Country'))
            or clean_string(props.get('country'))
        )
        region = (
            clean_string(props.get('Subregion'))
            or clean_string(props.get('Region'))
            or clean_string(props.get('region'))
        )

        vnum = (
            clean_string(props.get('Volcano_Number'))
            or clean_string(props.get('VolcanoNumber'))
            or clean_string(props.get('volcano_number'))
        )
        elevation = parse_int(
            props.get('Elevation')
            or props.get('elevation')
            or props.get('Elev')
        )
        vtype_raw = (
            clean_string(props.get('Primary_Volcano_Type'))
            or clean_string(props.get('Volcano_Type'))
            or clean_string(props.get('Type'))
        )
        vtype = VOLCANO_TYPE_MAP.get(vtype_raw, vtype_raw)

        last_eruption_raw = (
            clean_string(props.get('Last_Eruption_Year'))
            or clean_string(props.get('LastEruptionYear'))
            or clean_string(props.get('last_eruption_year'))
        )
        last_eruption_year = parse_int(last_eruption_raw)

        volcanoes.append({
            'volcano_number': vnum,
            'name': name,
            'latitude': max(-90.0, min(90.0, lat)),
            'longitude': max(-180.0, min(180.0, lon)),
            'country': country,
            'region': region,
            'elevation_m': elevation,
            'volcano_type': vtype,
            'last_eruption_year': last_eruption_year,
            'properties': props,
        })

    return volcanoes


def _parse_eruptions_geojson(filepath):
    """Parse eruption records GeoJSON if available.
    Returns dict keyed by volcano_number -> list of eruption dicts.
    """
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Volcano] Could not parse eruptions file: {e}")
        return {}

    eruptions_by_volcano = {}
    for feat in data.get('features', []):
        props = feat.get('properties', {})

        vnum = clean_string(
            props.get('Volcano_Number')
            or props.get('VolcanoNumber')
            or props.get('volcano_number')
        )
        if not vnum:
            continue

        start_year = parse_int(
            props.get('Start_Year')
            or props.get('StartYear')
            or props.get('start_year')
        )
        end_year = parse_int(
            props.get('End_Year')
            or props.get('EndYear')
            or props.get('end_year')
        )
        vei = parse_int(
            props.get('VEI')
            or props.get('vei')
        )
        eruption_id = clean_string(
            props.get('Eruption_Number')
            or props.get('EruptionNumber')
        )

        start_month = parse_int(props.get('Start_Month') or props.get('StartMonth'))
        start_day = parse_int(props.get('Start_Day') or props.get('StartDay'))

        start_date = None
        if start_year is not None:
            month = start_month if start_month and 1 <= start_month <= 12 else 1
            day = start_day if start_day and 1 <= start_day <= 31 else 1
            try:
                start_date = f"{start_year:04d}-{month:02d}-{day:02d}"
            except (ValueError, TypeError):
                start_date = None

        eruptions_by_volcano.setdefault(vnum, []).append({
            'eruption_id': eruption_id,
            'start_year': start_year,
            'end_year': end_year,
            'start_date': start_date,
            'vei': vei,
        })

    return eruptions_by_volcano


def load(min_year=1976):
    """Load volcano data, cross-reference eruptions with locations.
    Return GeoJSON features with Point geometry at volcano location.
    """
    volcanoes_path = os.path.join(RAW_DIR, 'gvp_holocene_volcanoes.json')
    eruptions_path = os.path.join(RAW_DIR, 'gvp_eruptions.json')

    if not os.path.exists(volcanoes_path):
        alt_paths = glob.glob(os.path.join(RAW_DIR, '*.json'))
        if alt_paths:
            volcanoes_path = alt_paths[0]
            print(f"[Volcano] Using alternative file: {volcanoes_path}")
        else:
            print(f"[Volcano] No data files found in {RAW_DIR}. Run with --download first.")
            return []

    print(f"[Volcano] Parsing volcano locations from {volcanoes_path}")
    try:
        volcanoes = parse_volcanoes_geojson(volcanoes_path)
    except Exception as e:
        print(f"[Volcano] Failed to parse volcano data: {e}")
        return []

    print(f"[Volcano] Loaded {len(volcanoes)} volcanoes")

    eruptions_by_volcano = _parse_eruptions_geojson(eruptions_path)
    has_eruptions = bool(eruptions_by_volcano)
    if has_eruptions:
        total_eruptions = sum(len(v) for v in eruptions_by_volcano.values())
        print(f"[Volcano] Loaded {total_eruptions} eruption records for {len(eruptions_by_volcano)} volcanoes")
    else:
        print("[Volcano] No separate eruption records; using last-eruption-year from volcano data")

    features = []
    skipped = 0

    for vol in volcanoes:
        try:
            lat = vol['latitude']
            lon = vol['longitude']
            vnum = vol.get('volcano_number')

            if has_eruptions and vnum and vnum in eruptions_by_volcano:
                for erupt in eruptions_by_volcano[vnum]:
                    yr = erupt.get('start_year')
                    if min_year and yr is not None and yr < min_year:
                        continue

                    vei = erupt.get('vei')
                    vei_desc = VEI_DESCRIPTIONS.get(vei, f'VEI {vei}') if vei is not None else None

                    event_id = slugify_id(
                        'eruption',
                        yr,
                        f"{vol['name']}_{erupt.get('eruption_id', '')}",
                    )

                    properties = {
                        'id': event_id,
                        'name': f"{vol['name']} eruption ({yr or '?'})",
                        'volcano_name': vol['name'],
                        'type': 'volcanic_eruption',
                        'subtype': vol.get('volcano_type'),
                        'year': yr,
                        'start_date': erupt.get('start_date'),
                        'end_year': erupt.get('end_year'),
                        'country': vol.get('country'),
                        'region': vol.get('region'),
                        'latitude': lat,
                        'longitude': lon,
                        'elevation_m': vol.get('elevation_m'),
                        'severity': vei,
                        'severity_unit': 'VEI',
                        'severity_label': vei_desc,
                        'deaths': None,
                        'source': 'Smithsonian GVP',
                        'source_id': vnum,
                        'eruption_id': erupt.get('eruption_id'),
                    }

                    features.append(point_feature(lon, lat, properties))

            else:
                yr = vol.get('last_eruption_year')
                if min_year and yr is not None and yr < min_year:
                    continue
                if yr is None:
                    continue

                event_id = slugify_id('eruption', yr, vol['name'])

                properties = {
                    'id': event_id,
                    'name': f"{vol['name']} eruption ({yr})",
                    'volcano_name': vol['name'],
                    'type': 'volcanic_eruption',
                    'subtype': vol.get('volcano_type'),
                    'year': yr,
                    'start_date': None,
                    'country': vol.get('country'),
                    'region': vol.get('region'),
                    'latitude': lat,
                    'longitude': lon,
                    'elevation_m': vol.get('elevation_m'),
                    'severity': None,
                    'severity_unit': 'VEI',
                    'severity_label': None,
                    'deaths': None,
                    'source': 'Smithsonian GVP',
                    'source_id': vnum,
                }

                features.append(point_feature(lon, lat, properties))

        except Exception as e:
            skipped += 1
            continue

    print(f"[Volcano] Produced {len(features)} features ({skipped} volcanoes skipped)")
    return features


def main():
    parser = argparse.ArgumentParser(description='Smithsonian GVP Volcano importer')
    parser.add_argument('--download', action='store_true', help='Download raw data from Smithsonian GVP')
    parser.add_argument('--min-year', type=int, default=1976, help='Minimum eruption year (default: 1976)')
    parser.add_argument('--output', type=str, default=None, help='Write GeoJSON output to file')
    args = parser.parse_args()

    if args.download:
        download()

    features = load(min_year=args.min_year)
    print(f"[Volcano] {len(features)} total features returned")

    if args.output and features:
        collection = {
            'type': 'FeatureCollection',
            'features': features,
        }
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(collection, f, ensure_ascii=False)
        print(f"[Volcano] Wrote {args.output}")

    return features


if __name__ == '__main__':
    main()
