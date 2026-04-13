import json
import os
from datetime import datetime


TYPE_TO_FILENAME = {
    "earthquake": "earthquakes.geojson",
    "hurricane": "hurricanes.geojson",
    "wildfire": "wildfires.geojson",
    "drought": "droughts.geojson",
    "flooding": "floods.geojson",
    "volcanic_eruption": "volcanoes.geojson",
    "tsunami": "tsunamis.geojson",
    "tornado": "tornadoes.geojson",
    "ice_storm": "winter.geojson",
    "blizzard": "winter.geojson",
    "cold_wave": "winter.geojson",
    "heatwave": "heatwaves.geojson",
}


def _strip_nulls(props):
    """Remove keys with None values from a properties dict."""
    if not props:
        return {}
    return {k: v for k, v in props.items() if v is not None}


def save_geojson(features, filepath, sort_by_year=True):
    """Save list of GeoJSON features as a FeatureCollection.

    - Remove null/None values from properties
    - Sort by year if requested
    - Write with minimal indentation for size
    """
    cleaned = []
    for f in features:
        feat = dict(f)
        feat["properties"] = _strip_nulls(feat.get("properties"))
        cleaned.append(feat)

    if sort_by_year:
        cleaned.sort(
            key=lambda f: (
                f["properties"].get("year") or 0,
                f["properties"].get("name") or "",
            )
        )

    collection = {
        "type": "FeatureCollection",
        "features": cleaned,
    }

    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(collection, fh, indent=1, ensure_ascii=False)

    return len(cleaned)


def save_metadata(all_features, filepath):
    """Generate and save metadata.json with counts, ranges, timestamp."""
    counts_by_type = {}
    source_counts = {}
    years = []

    for f in all_features:
        props = f.get("properties", {})

        dtype = props.get("type") or "unknown"
        counts_by_type[dtype] = counts_by_type.get(dtype, 0) + 1

        sources = props.get("sources", [])
        if isinstance(sources, str):
            sources = [sources]
        for src in sources:
            source_counts[src] = source_counts.get(src, 0) + 1

        year = props.get("year")
        if year is not None:
            try:
                years.append(int(year))
            except (ValueError, TypeError):
                pass

    metadata = {
        "total_records": len(all_features),
        "counts_by_type": dict(sorted(counts_by_type.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "min_year": min(years) if years else None,
        "max_year": max(years) if years else None,
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, ensure_ascii=False)

    return metadata


def split_by_type(features):
    """Split features into dict keyed by disaster type."""
    result = {}
    for f in features:
        props = f.get("properties", {})
        dtype = props.get("type") or "unknown"
        if dtype not in result:
            result[dtype] = []
        result[dtype].append(f)
    return result
