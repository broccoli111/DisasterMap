from difflib import SequenceMatcher
from scripts.utils.normalize import parse_int


GEOMETRY_PRIORITY = ["USGS", "IBTrACS", "NOAA", "Smithsonian", "NASA", "EM-DAT"]
IMPACT_PRIORITY = ["EM-DAT", "NOAA", "USGS", "Smithsonian", "NASA"]


def similarity(a, b):
    """String similarity ratio 0-1."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()


def _get_prop(feature, key, default=None):
    """Safely get a property from a GeoJSON feature."""
    props = feature.get("properties") if feature else None
    if props is None:
        return default
    return props.get(key, default)


def records_match(a, b, name_threshold=0.7):
    """Check if two feature records represent the same event.

    Match by: type, year, country similarity, name similarity.
    """
    type_a = _get_prop(a, "type")
    type_b = _get_prop(b, "type")
    if type_a != type_b:
        return False

    year_a = parse_int(_get_prop(a, "year"))
    year_b = parse_int(_get_prop(b, "year"))
    if year_a is not None and year_b is not None and abs(year_a - year_b) > 1:
        return False

    name_a = _get_prop(a, "name") or ""
    name_b = _get_prop(b, "name") or ""
    if name_a and name_b:
        name_sim = similarity(name_a, name_b)
        if name_sim >= name_threshold:
            return True
        la, lb = name_a.lower(), name_b.lower()
        if la in lb or lb in la:
            return True

    country_a = _get_prop(a, "country") or ""
    country_b = _get_prop(b, "country") or ""
    if country_a and country_b:
        country_sim = similarity(country_a, country_b)
        if country_sim >= 0.85:
            if name_a and name_b:
                return similarity(name_a, name_b) >= (name_threshold * 0.7)
            return year_a == year_b

    return False


def _source_priority(source_name, priority_list):
    """Return priority index for a source (lower = higher priority)."""
    try:
        return priority_list.index(source_name)
    except ValueError:
        return len(priority_list)


def _best_source(sources, priority_list):
    """Pick the highest-priority source from a list."""
    if not sources:
        return None
    return min(sources, key=lambda s: _source_priority(s, priority_list))


def merge_records(primary, secondary):
    """Merge two matching records. Keep geometry from higher-priority source.
    Fill missing impact fields from secondary. Combine sources arrays.
    """
    p_props = dict(primary.get("properties", {}))
    s_props = dict(secondary.get("properties", {}))

    p_sources = p_props.get("sources", [])
    s_sources = s_props.get("sources", [])
    if isinstance(p_sources, str):
        p_sources = [p_sources]
    if isinstance(s_sources, str):
        s_sources = [s_sources]
    all_sources = list(p_sources)
    for s in s_sources:
        if s not in all_sources:
            all_sources.append(s)

    geo_source = _best_source(all_sources, GEOMETRY_PRIORITY)
    if geo_source in s_sources and geo_source not in p_sources:
        geometry = secondary.get("geometry")
    else:
        geometry = primary.get("geometry")

    impact_fields = [
        "deaths", "injured", "affected", "damage_usd",
        "homeless", "displaced", "total_affected",
    ]
    impact_source = _best_source(all_sources, IMPACT_PRIORITY)
    for field in impact_fields:
        if impact_source in s_sources and impact_source not in p_sources:
            if s_props.get(field) is not None:
                p_props[field] = s_props[field]
        if p_props.get(field) is None and s_props.get(field) is not None:
            p_props[field] = s_props[field]

    for key, val in s_props.items():
        if key not in p_props or p_props[key] is None:
            p_props[key] = val

    p_props["sources"] = all_sources

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": p_props,
    }


def deduplicate(features, name_threshold=0.7):
    """Deduplicate a list of features. Return merged list."""
    if not features:
        return []

    groups = {}
    for f in features:
        dtype = _get_prop(f, "type") or "unknown"
        year = parse_int(_get_prop(f, "year")) or 0
        key = (dtype, year)
        if key not in groups:
            groups[key] = []
        groups[key].append(f)

    for dtype_year_key in list(groups.keys()):
        dtype, year = dtype_year_key
        if year > 0:
            adjacent_key = (dtype, year - 1)
            if adjacent_key in groups:
                groups[dtype_year_key] = groups[dtype_year_key] + groups[adjacent_key]
                del groups[adjacent_key]

    merged_all = []
    seen_ids = set()

    for key in sorted(groups.keys()):
        group = groups[key]
        merged_group = []
        for feat in group:
            feat_id = id(feat)
            if feat_id in seen_ids:
                continue

            matched = False
            for i, existing in enumerate(merged_group):
                if records_match(existing, feat, name_threshold):
                    merged_group[i] = merge_records(existing, feat)
                    matched = True
                    break

            if not matched:
                merged_group.append(feat)
            seen_ids.add(feat_id)

        merged_all.extend(merged_group)

    return merged_all
