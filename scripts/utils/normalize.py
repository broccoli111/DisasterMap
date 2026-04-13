import re
import unicodedata
from datetime import datetime


def clean_string(s):
    """Strip, normalize unicode, collapse whitespace. Return None if empty."""
    if s is None:
        return None
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else None


def parse_int(val, default=None):
    """Parse value to int, return default on failure."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError, OverflowError):
        return default


def parse_float(val, default=None):
    """Parse value to float, return default on failure."""
    if val is None:
        return default
    try:
        result = float(val)
        if result != result:  # NaN check
            return default
        return result
    except (ValueError, TypeError, OverflowError):
        return default


_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y%m%d",
    "%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
]


def parse_date(val, formats=None):
    """Try multiple date formats, return 'YYYY-MM-DD' string or None."""
    if val is None:
        return None
    if not isinstance(val, str):
        val = str(val)
    val = val.strip()
    if not val:
        return None

    if formats is None:
        formats = _DATE_FORMATS

    for fmt in formats:
        try:
            dt = datetime.strptime(val, fmt)
            if fmt == "%Y":
                return f"{dt.year}-01-01"
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_year(val):
    """Extract year as int from various date formats."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        yr = int(val)
        if 1000 <= yr <= 9999:
            return yr
        return None

    s = str(val).strip()
    if not s:
        return None

    date_str = parse_date(s)
    if date_str:
        return int(date_str[:4])

    match = re.search(r"\b(\d{4})\b", s)
    if match:
        yr = int(match.group(1))
        if 1000 <= yr <= 9999:
            return yr
    return None


def slugify_id(prefix, year, name):
    """Create a unique slug like 'eq_2011_tohoku_japan'."""
    parts = []
    if prefix:
        parts.append(str(prefix).lower().strip())
    if year is not None:
        parts.append(str(int(year)))
    if name:
        slug = str(name).lower().strip()
        slug = unicodedata.normalize("NFKD", slug)
        slug = slug.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")
        if slug:
            parts.append(slug)
    result = "_".join(parts)
    return result[:60]


_COUNTRY_MAP = {
    "us": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "uae": "United Arab Emirates",
    "drc": "Democratic Republic of the Congo",
    "congo, dem. rep.": "Democratic Republic of the Congo",
    "congo (democratic republic of the)": "Democratic Republic of the Congo",
    "republic of korea": "South Korea",
    "korea, republic of": "South Korea",
    "korea (the republic of)": "South Korea",
    "korea, dem. people's rep.": "North Korea",
    "russian federation": "Russia",
    "iran (islamic republic of)": "Iran",
    "iran, islamic rep.": "Iran",
    "syrian arab republic": "Syria",
    "viet nam": "Vietnam",
    "lao people's democratic republic": "Laos",
    "myanmar (burma)": "Myanmar",
    "china, people's rep.": "China",
    "china (people's republic of)": "China",
    "taiwan (province of china)": "Taiwan",
    "philippines (the)": "Philippines",
    "netherlands (the)": "Netherlands",
    "czech republic": "Czechia",
    "cabo verde": "Cape Verde",
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "eswatini": "Eswatini",
    "swaziland": "Eswatini",
    "timor-leste": "East Timor",
    "brunei darussalam": "Brunei",
    "bolivia (plurinational state of)": "Bolivia",
    "venezuela (bolivarian republic of)": "Venezuela",
    "tanzania, united rep.": "Tanzania",
}


def normalize_country(name):
    """Normalize common country name variations."""
    if name is None:
        return None
    cleaned = clean_string(name)
    if not cleaned:
        return None
    lookup = cleaned.lower()
    if lookup in _COUNTRY_MAP:
        return _COUNTRY_MAP[lookup]
    return cleaned


_DISASTER_TYPE_MAP = {
    "earthquake": "earthquake",
    "seismic": "earthquake",
    "quake": "earthquake",
    "eq": "earthquake",
    "hurricane": "hurricane",
    "typhoon": "hurricane",
    "cyclone": "hurricane",
    "tropical storm": "hurricane",
    "tropical cyclone": "hurricane",
    "tc": "hurricane",
    "wildfire": "wildfire",
    "forest fire": "wildfire",
    "bush fire": "wildfire",
    "bushfire": "wildfire",
    "wild fire": "wildfire",
    "fire": "wildfire",
    "drought": "drought",
    "flood": "flooding",
    "flooding": "flooding",
    "flash flood": "flooding",
    "riverine flood": "flooding",
    "coastal flood": "flooding",
    "river flood": "flooding",
    "volcanic eruption": "volcanic_eruption",
    "volcano": "volcanic_eruption",
    "volcanic": "volcanic_eruption",
    "eruption": "volcanic_eruption",
    "volcanic activity": "volcanic_eruption",
    "tsunami": "tsunami",
    "tidal wave": "tsunami",
    "tornado": "tornado",
    "tornadoes": "tornado",
    "ice storm": "ice_storm",
    "blizzard": "blizzard",
    "snowstorm": "blizzard",
    "snow storm": "blizzard",
    "winter storm": "blizzard",
    "cold wave": "cold_wave",
    "cold snap": "cold_wave",
    "extreme cold": "cold_wave",
    "freeze": "cold_wave",
    "frost": "cold_wave",
    "severe winter": "cold_wave",
    "heatwave": "heatwave",
    "heat wave": "heatwave",
    "extreme heat": "heatwave",
    "heat": "heatwave",
    "extreme temperature": "heatwave",
}


def normalize_disaster_type(raw_type):
    """Map various raw type strings to our canonical types."""
    if raw_type is None:
        return None
    cleaned = clean_string(raw_type)
    if not cleaned:
        return None
    lookup = cleaned.lower()
    if lookup in _DISASTER_TYPE_MAP:
        return _DISASTER_TYPE_MAP[lookup]
    for key, canonical in _DISASTER_TYPE_MAP.items():
        if key in lookup or lookup in key:
            return canonical
    return lookup
