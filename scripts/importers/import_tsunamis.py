"""
NOAA National Centers for Environmental Information - Historical Tsunami Database.
URL: https://www.ngdc.noaa.gov/hazel/view/hazards/tsunami/event-search
API: https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1/tsunamis/events?minYear=1976&maxYear=2025
"""

import os
import sys
import json
import math
import logging

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.utils.normalize import parse_int, parse_float, normalize_country, slugify_id
from scripts.utils.geo import line_feature

logger = logging.getLogger(__name__)

RAW_DIR = 'raw/usgs'
RAW_FILE = os.path.join(RAW_DIR, 'tsunamis.json')
API_URL = 'https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1/tsunamis/events'
REQUEST_TIMEOUT = 60

CAUSE_LABELS = {
    1: 'Earthquake',
    2: 'Questionable Earthquake',
    3: 'Earthquake and Landslide',
    4: 'Volcano and Earthquake',
    5: 'Volcano, Earthquake, and Landslide',
    6: 'Volcano',
    7: 'Volcano and Landslide',
    8: 'Landslide',
    9: 'Meteorological',
    10: 'Explosion',
    11: 'Astronomical Tide',
}


def download(min_year=1976):
    """Download tsunami events from NOAA NCEI Hazard Services API.
    Saves raw JSON response to raw/usgs/tsunamis.json.
    """
    os.makedirs(RAW_DIR, exist_ok=True)
    params = {
        'minYear': min_year,
        'maxYear': 2025,
    }
    logger.info("Fetching tsunamis from NOAA NCEI: %s", API_URL)
    try:
        resp = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and 'items' in data:
            events = data['items']
        elif isinstance(data, list):
            events = data
        else:
            events = data
        with open(RAW_FILE, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        logger.info(
            "Saved %d tsunami events to %s",
            len(events) if isinstance(events, list) else 0,
            RAW_FILE,
        )
        return events
    except requests.exceptions.Timeout:
        logger.warning("NOAA API request timed out after %ds", REQUEST_TIMEOUT)
        return None
    except requests.exceptions.ConnectionError as exc:
        logger.warning("Connection error reaching NOAA API: %s", exc)
        return None
    except requests.exceptions.HTTPError as exc:
        logger.warning("NOAA API returned error: %s", exc)
        return None
    except (ValueError, KeyError) as exc:
        logger.warning("Failed to parse NOAA API response: %s", exc)
        return None


def _load_raw():
    """Load raw tsunami JSON from disk."""
    if not os.path.exists(RAW_FILE):
        return None
    try:
        with open(RAW_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as exc:
        logger.warning("Failed to read %s: %s", RAW_FILE, exc)
        return None


def _destination_point(lon, lat, bearing_deg, distance_km):
    """Compute destination point given start, bearing (degrees), and distance (km)."""
    R = 6371.0
    d = distance_km / R
    br = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(br)
    )
    lon2 = lon1 + math.atan2(
        math.sin(br) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lon2), math.degrees(lat2)


def _estimate_coast_bearing(lon, lat):
    """Heuristic bearing from an offshore epicenter toward the nearest coast."""
    if 100 < lon < 180 and -10 < lat < 50:
        return 300
    if 120 < lon < 180 and lat < -10:
        return 220
    if -180 < lon < -100 and lat > 0:
        return 90
    if -90 < lon < -30 and lat > 0:
        return 270
    if -90 < lon < -30 and lat < 0:
        return 270
    if 20 < lon < 100 and lat > 0:
        return 0
    if 20 < lon < 80 and lat < 0:
        return 315
    return 45


def _make_tsunami_linestring(epicenter_lon, epicenter_lat, max_height=None):
    """Create a coordinate list representing tsunami wave propagation.
    Length scales with wave height. Returns list of [lon, lat] pairs.
    """
    propagation_km = 100
    if max_height is not None and max_height > 0:
        propagation_km = min(50 + max_height * 30, 500)

    coast_bearing = _estimate_coast_bearing(epicenter_lon, epicenter_lat)
    num_points = 6
    coords = []
    for i in range(num_points):
        frac = i / max(num_points - 1, 1)
        dist = propagation_km * frac
        lon, lat = _destination_point(epicenter_lon, epicenter_lat, coast_bearing, dist)
        coords.append([round(lon, 3), round(lat, 3)])

    if len(coords) < 2:
        end_lon, end_lat = _destination_point(
            epicenter_lon, epicenter_lat, coast_bearing, propagation_km
        )
        coords = [
            [round(epicenter_lon, 3), round(epicenter_lat, 3)],
            [round(end_lon, 3), round(end_lat, 3)],
        ]
    return coords


def _parse_event(event):
    """Parse a single NOAA tsunami event dict into a GeoJSON Feature.
    Returns None if the event lacks usable coordinates.
    """
    lat = parse_float(event.get('latitude'))
    lon = parse_float(event.get('longitude'))
    if lat is None or lon is None:
        return None

    year = parse_int(event.get('year'), default=0)
    country = normalize_country(event.get('country', '') or '') or ''
    location = (event.get('locationName') or event.get('location') or '').strip()
    region = location if location else country

    max_height = parse_float(event.get('maxWaterHeight'))
    eq_mag = parse_float(event.get('eqMagnitude') or event.get('magnitude'))
    deaths = parse_int(event.get('deaths') or event.get('totalDeaths'), default=0)
    injuries = parse_int(event.get('injuries') or event.get('totalInjuries'), default=0)
    damage = parse_float(
        event.get('damageMillionsDollars') or event.get('totalDamageMillionsDollars')
    )

    cause_code = parse_int(event.get('causeCode'), default=0)
    cause = CAUSE_LABELS.get(cause_code, event.get('cause', 'Unknown'))

    name_parts = []
    if year:
        name_parts.append(str(year))
    if location:
        name_parts.append(location)
    elif country:
        name_parts.append(country)
    name_parts.append('Tsunami')
    name = ' '.join(name_parts)

    severity_parts = []
    if max_height is not None:
        severity_parts.append(f"{max_height}m wave")
    if eq_mag is not None:
        severity_parts.append(f"{eq_mag} Mw trigger")
    severity = '; '.join(severity_parts) if severity_parts else ''

    description_parts = []
    if cause and cause != 'Unknown':
        description_parts.append(f"Cause: {cause}.")
    if max_height is not None:
        description_parts.append(f"Maximum water height: {max_height}m.")
    if deaths:
        description_parts.append(f"Deaths: {deaths:,}.")
    if injuries:
        description_parts.append(f"Injuries: {injuries:,}.")
    if damage is not None:
        description_parts.append(f"Damage: ${damage}M.")
    description = ' '.join(description_parts)

    coords = _make_tsunami_linestring(lon, lat, max_height)

    props = {
        'id': slugify_id('tsu', year, location or country or f"{lat}_{lon}"),
        'name': name,
        'type': 'tsunami',
        'year': year,
        'country': country,
        'region': region,
        'severity': severity,
        'deaths': deaths,
        'description': description,
        'source': 'NOAA NCEI',
    }
    if max_height is not None:
        props['max_water_height_m'] = max_height
    if eq_mag is not None:
        props['magnitude'] = eq_mag

    return line_feature(coords, props)


def load(min_year=1976):
    """Load tsunami data from downloaded JSON or fetch from API.
    Falls back to existing project data if API is unavailable.
    Returns a list of GeoJSON Feature dicts.
    """
    events = _load_raw()

    if events is None:
        logger.info("No cached tsunami data, attempting API download...")
        events = download(min_year=min_year)

    if events is not None and isinstance(events, list):
        features = []
        for event in events:
            try:
                feat = _parse_event(event)
                if feat is None:
                    continue
                event_year = feat['properties'].get('year', 0)
                if event_year and event_year < min_year:
                    continue
                features.append(feat)
            except Exception as exc:
                logger.debug("Skipping unparseable tsunami event: %s", exc)
                continue
        if features:
            logger.info("Loaded %d tsunami features from NOAA NCEI data", len(features))
            return features
        logger.info("NOAA data parsed but yielded 0 features, trying fallback")

    return load_fallback(min_year=min_year)


def load_fallback(min_year=1976):
    """Load tsunami features from any available local data source.
    Checks existing GeoJSON exports, then raw CSV/JSON in raw directories.
    """
    for path in [
        'data/disasters.geojson',
        'data/all_disasters.geojson',
        'data/tsunamis.geojson',
    ]:
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            features = [
                feat for feat in data.get('features', [])
                if feat.get('properties', {}).get('type') == 'tsunami'
                and feat.get('properties', {}).get('year', 0) >= min_year
            ]
            if features:
                logger.info(
                    "Loaded %d tsunami features from fallback %s",
                    len(features), path,
                )
                return features
        except (json.JSONDecodeError, IOError):
            continue

    raw_candidates = [
        os.path.join(RAW_DIR, 'tsunamis.csv'),
        os.path.join(RAW_DIR, 'tsunami_events.json'),
        'raw/emdat/tsunamis.csv',
    ]
    for path in raw_candidates:
        if not os.path.exists(path):
            continue
        try:
            if path.endswith('.json'):
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    features = []
                    for evt in raw:
                        feat = _parse_event(evt)
                        if feat and feat['properties'].get('year', 0) >= min_year:
                            features.append(feat)
                    if features:
                        return features
            elif path.endswith('.csv'):
                features = _parse_csv_fallback(path, min_year)
                if features:
                    return features
        except Exception as exc:
            logger.debug("Fallback file %s failed: %s", path, exc)
            continue

    logger.warning("No tsunami data found from any source")
    return []


def _parse_csv_fallback(path, min_year):
    """Best-effort CSV parsing for tsunami data without pandas."""
    import csv
    features = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lat = parse_float(row.get('latitude') or row.get('LATITUDE'))
                lon = parse_float(row.get('longitude') or row.get('LONGITUDE'))
                if lat is None or lon is None:
                    continue
                year = parse_int(row.get('year') or row.get('YEAR'), default=0)
                if year < min_year:
                    continue
                country = row.get('country') or row.get('COUNTRY') or ''
                location = row.get('locationName') or row.get('LOCATION_NAME') or ''
                max_height = parse_float(row.get('maxWaterHeight') or row.get('WATER_HT'))
                deaths = parse_int(row.get('deaths') or row.get('DEATHS'), default=0)

                name = f"{year} {location or country} Tsunami"
                severity = f"{max_height}m wave" if max_height else ''
                coords = _make_tsunami_linestring(lon, lat, max_height)

                props = {
                    'id': slugify_id('tsu', year, location or country),
                    'name': name,
                    'type': 'tsunami',
                    'year': year,
                    'country': normalize_country(country) or country,
                    'region': location or country,
                    'severity': severity,
                    'deaths': deaths,
                    'description': '',
                    'source': 'NOAA NCEI',
                }
                features.append(line_feature(coords, props))
    except Exception as exc:
        logger.debug("CSV fallback parse failed: %s", exc)
    return features


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))
    features = load()
    print(f"Loaded {len(features)} tsunami features")
    if features:
        print(f"Sample: {json.dumps(features[0], indent=2)}")
