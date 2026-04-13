import math
import json

from shapely.geometry import Point, Polygon, LineString, MultiPolygon, mapping, shape
from shapely.ops import unary_union
from shapely import simplify as shapely_simplify


def point_feature(lon, lat, properties):
    """Create a GeoJSON Feature with Point geometry."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(lon), float(lat)],
        },
        "properties": dict(properties) if properties else {},
    }


def polygon_feature(coords, properties):
    """Create a GeoJSON Feature with Polygon geometry. coords = list of [lon,lat] pairs."""
    ring = [list(c) for c in coords]
    if ring and ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
        "properties": dict(properties) if properties else {},
    }


def line_feature(coords, properties):
    """Create a GeoJSON Feature with LineString geometry."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [list(c) for c in coords],
        },
        "properties": dict(properties) if properties else {},
    }


def bbox_to_polygon(minlon, minlat, maxlon, maxlat):
    """Convert bounding box to polygon coordinate ring."""
    return [
        [minlon, minlat],
        [maxlon, minlat],
        [maxlon, maxlat],
        [minlon, maxlat],
        [minlon, minlat],
    ]


def buffer_point(lon, lat, radius_km):
    """Create an approximate circular polygon around a point. Return coordinate ring."""
    num_points = 32
    coords = []
    earth_radius_km = 6371.0
    lat_rad = math.radians(lat)
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        dlat = (radius_km / earth_radius_km) * math.cos(angle)
        dlon = (radius_km / (earth_radius_km * math.cos(lat_rad))) * math.sin(angle)
        pt_lat = lat + math.degrees(dlat)
        pt_lon = lon + math.degrees(dlon)
        coords.append([pt_lon, pt_lat])
    coords.append(coords[0])
    return coords


def magnitude_to_radius_km(magnitude):
    """Estimate affected area radius from earthquake magnitude."""
    if magnitude is None:
        return 20.0
    try:
        mag = float(magnitude)
    except (ValueError, TypeError):
        return 20.0
    if mag < 5.0:
        return max(5.0, 4 * (mag - 3))
    elif mag < 6.0:
        return 20 + 30 * (mag - 5.0)
    elif mag < 7.0:
        return 50 + 50 * (mag - 6.0)
    elif mag < 8.0:
        return 100 + 100 * (mag - 7.0)
    elif mag < 9.0:
        return 200 + 200 * (mag - 8.0)
    else:
        return 400 + 200 * (mag - 9.0)


def simplify_geometry(geom, tolerance=0.01):
    """Simplify a shapely geometry to reduce point count."""
    if geom is None or geom.is_empty:
        return geom
    return shapely_simplify(geom, tolerance, preserve_topology=True)


def _round_coords_recursive(coords, precision):
    """Recursively round coordinates in a nested list structure."""
    if isinstance(coords, (int, float)):
        return round(coords, precision)
    if isinstance(coords, (list, tuple)):
        return [_round_coords_recursive(c, precision) for c in coords]
    return coords


def round_coords(feature, precision=3):
    """Round all coordinates in a GeoJSON feature to given decimal precision."""
    if feature is None:
        return feature
    result = dict(feature)
    geom = result.get("geometry")
    if geom and "coordinates" in geom:
        result["geometry"] = dict(geom)
        result["geometry"]["coordinates"] = _round_coords_recursive(
            geom["coordinates"], precision
        )
    return result


def feature_bounds(feature):
    """Get [minlon, minlat, maxlon, maxlat] from a GeoJSON feature."""
    if feature is None:
        return None
    geom = feature.get("geometry")
    if not geom or "coordinates" not in geom:
        return None

    def _extract_points(coords):
        if not coords:
            return []
        if isinstance(coords[0], (int, float)):
            return [coords]
        points = []
        for c in coords:
            points.extend(_extract_points(c))
        return points

    points = _extract_points(geom["coordinates"])
    if not points:
        return None

    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return [min(lons), min(lats), max(lons), max(lats)]
