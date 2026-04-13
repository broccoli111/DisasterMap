"""
Master pipeline runner for Global Natural Disaster Atlas.
Downloads, imports, normalizes, deduplicates, and exports disaster data.

Usage:
    python scripts/run_all.py                    # Run full pipeline
    python scripts/run_all.py --download         # Download raw data first
    python scripts/run_all.py --source usgs      # Only run USGS importer
    python scripts/run_all.py --type earthquakes  # Only process earthquakes
    python scripts/run_all.py --since 2000       # Only events from 2000+
    python scripts/run_all.py --fast             # Skip download, skip dedup
"""

import os
import sys
import argparse
import time
import traceback
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from scripts.importers.import_usgs import load as load_usgs, download as download_usgs
from scripts.importers.import_ibtracs import load as load_ibtracs, download as download_ibtracs
from scripts.importers.import_volcano import load as load_volcano, download as download_volcano
from scripts.importers.import_tsunamis import load as load_tsunamis, download as download_tsunamis
from scripts.importers.import_noaa_events import load as load_noaa_events, download as download_noaa_events
from scripts.importers.import_firms import load as load_firms, download as download_firms
from scripts.importers.import_floods import load as load_floods, download as download_floods
from scripts.importers.import_climate import load as load_climate, download as download_climate
from scripts.importers.import_emdat import load as load_emdat, download as download_emdat

from scripts.utils.export import save_geojson, save_metadata, split_by_type, TYPE_TO_FILENAME
from scripts.utils.dedupe import deduplicate
from scripts.utils.geo import round_coords

DATA_DIR = 'data'

IMPORTERS = {
    'usgs': {'download': download_usgs, 'load': load_usgs, 'types': ['earthquake']},
    'ibtracs': {'download': download_ibtracs, 'load': load_ibtracs, 'types': ['hurricane']},
    'volcano': {'download': download_volcano, 'load': load_volcano, 'types': ['volcanic_eruption']},
    'tsunamis': {'download': download_tsunamis, 'load': load_tsunamis, 'types': ['tsunami']},
    'noaa_events': {'download': download_noaa_events, 'load': load_noaa_events, 'types': ['tornado', 'ice_storm', 'blizzard', 'cold_wave']},
    'firms': {'download': download_firms, 'load': load_firms, 'types': ['wildfire']},
    'floods': {'download': download_floods, 'load': load_floods, 'types': ['flooding']},
    'climate': {'download': download_climate, 'load': load_climate, 'types': ['heatwave', 'cold_wave', 'drought']},
    'emdat': {'download': download_emdat, 'load': load_emdat, 'types': ['all']},
}

TYPE_ALIASES = {
    'earthquakes': 'earthquake', 'earthquake': 'earthquake',
    'hurricane': 'hurricane', 'hurricanes': 'hurricane',
    'typhoon': 'hurricane', 'cyclone': 'hurricane',
    'wildfire': 'wildfire', 'wildfires': 'wildfire',
    'fire': 'wildfire', 'fires': 'wildfire',
    'drought': 'drought', 'droughts': 'drought',
    'flood': 'flooding', 'floods': 'flooding', 'flooding': 'flooding',
    'volcano': 'volcanic_eruption', 'volcanoes': 'volcanic_eruption',
    'volcanic_eruption': 'volcanic_eruption', 'eruption': 'volcanic_eruption',
    'tsunami': 'tsunami', 'tsunamis': 'tsunami',
    'tornado': 'tornado', 'tornadoes': 'tornado',
    'heatwave': 'heatwave', 'heatwaves': 'heatwave',
    'cold_wave': 'cold_wave', 'blizzard': 'blizzard',
    'ice_storm': 'ice_storm',
}


def parse_args():
    parser = argparse.ArgumentParser(
        description='Global Natural Disaster Atlas - Data Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_all.py                     Full pipeline
  python scripts/run_all.py --download          Download then import
  python scripts/run_all.py --source usgs       Only USGS earthquakes
  python scripts/run_all.py --type earthquakes  Filter to earthquakes
  python scripts/run_all.py --since 2000        Events from 2000+
  python scripts/run_all.py --fast              Skip download & dedup
        """,
    )
    parser.add_argument('--download', action='store_true',
                        help='Download raw data from sources before importing')
    parser.add_argument('--source', type=str, default=None,
                        help='Only run a specific source importer (usgs, ibtracs, etc.)')
    parser.add_argument('--type', type=str, default=None,
                        help='Only process a specific disaster type (earthquake, hurricane, etc.)')
    parser.add_argument('--since', type=int, default=1976,
                        help='Minimum year filter (default: 1976)')
    parser.add_argument('--fast', action='store_true',
                        help='Skip download and deduplication steps')
    parser.add_argument('--output', type=str, default=None,
                        help='Override output directory (default: data/)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    return parser.parse_args()


def _call_download(download_fn, min_year):
    """Call a download function, introspecting whether it accepts min_year."""
    try:
        varnames = download_fn.__code__.co_varnames
        if 'min_year' in varnames:
            download_fn(min_year=min_year)
        else:
            download_fn()
    except TypeError:
        download_fn()


def _call_load(load_fn, min_year):
    """Call a load function, introspecting whether it accepts min_year."""
    try:
        varnames = load_fn.__code__.co_varnames
        if 'min_year' in varnames:
            return load_fn(min_year=min_year)
        return load_fn()
    except TypeError:
        return load_fn()


def _validate_feature(feature):
    """Basic validation that a feature has required GeoJSON structure."""
    if not isinstance(feature, dict):
        return False
    if feature.get('type') != 'Feature':
        return False
    geom = feature.get('geometry')
    if not isinstance(geom, dict) or 'type' not in geom or 'coordinates' not in geom:
        return False
    props = feature.get('properties')
    if not isinstance(props, dict):
        return False
    return True


def main():
    args = parse_args()
    start_time = time.time()
    output_dir = args.output or DATA_DIR

    print("=" * 60)
    print("  Global Natural Disaster Atlas - Data Pipeline")
    print("=" * 60)
    print()
    print(f"  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Min year:   {args.since}")
    print(f"  Output dir: {os.path.abspath(output_dir)}")
    if args.source:
        print(f"  Source:     {args.source}")
    if args.type:
        print(f"  Type:       {args.type}")
    if args.fast:
        print(f"  Mode:       fast (skip download & dedup)")
    print()

    os.makedirs(output_dir, exist_ok=True)

    importers_to_run = IMPORTERS
    if args.source:
        if args.source in IMPORTERS:
            importers_to_run = {args.source: IMPORTERS[args.source]}
        else:
            print(f"  ERROR: Unknown source '{args.source}'")
            print(f"  Available sources: {', '.join(sorted(IMPORTERS.keys()))}")
            sys.exit(1)

    # --- Step 1: Download ---
    if args.download and not args.fast:
        print(">>> DOWNLOADING RAW DATA")
        print("-" * 40)
        for name, imp in importers_to_run.items():
            try:
                print(f"  Downloading: {name}...", end=' ', flush=True)
                _call_download(imp['download'], args.since)
                print("OK")
            except Exception as exc:
                print(f"WARN: {exc}")
                if args.verbose:
                    traceback.print_exc()
        print()

    # --- Step 2: Import ---
    print(">>> IMPORTING DATA")
    print("-" * 40)
    all_features = []
    source_counts = {}

    for name, imp in importers_to_run.items():
        try:
            print(f"  Loading: {name}...", end=' ', flush=True)
            features = _call_load(imp['load'], args.since)

            if features is None:
                features = []
            if not isinstance(features, list):
                print(f"WARN: {name} returned non-list ({type(features).__name__}), skipping")
                source_counts[name] = 0
                continue

            valid = [f for f in features if _validate_feature(f)]
            invalid_count = len(features) - len(valid)

            source_counts[name] = len(valid)
            all_features.extend(valid)

            status = f"{len(valid):,} features"
            if invalid_count:
                status += f" ({invalid_count} invalid skipped)"
            print(status)
        except Exception as exc:
            print(f"FAILED: {exc}")
            if args.verbose:
                traceback.print_exc()
            source_counts[name] = 0

    print(f"\n  Total imported: {len(all_features):,} features")
    print()

    if not all_features:
        print("  WARNING: No features imported from any source.")
        print("  Writing empty output files.")
        print()

    # --- Step 3: Filter by type ---
    if args.type:
        target = TYPE_ALIASES.get(args.type.lower(), args.type.lower())
        before = len(all_features)
        all_features = [
            f for f in all_features
            if f.get('properties', {}).get('type') == target
        ]
        print(f">>> FILTERED by type '{target}': {before:,} -> {len(all_features):,}")
        print()

    # --- Step 4: Deduplicate ---
    if not args.fast and len(all_features) > 1:
        print(">>> DEDUPLICATING")
        print("-" * 40)
        before = len(all_features)
        try:
            all_features = deduplicate(all_features)
        except Exception as exc:
            print(f"  WARN: Deduplication failed ({exc}), keeping all features")
            if args.verbose:
                traceback.print_exc()
        after = len(all_features)
        removed = before - after
        print(f"  Before: {before:,} -> After: {after:,} (removed {removed:,} duplicates)")
        print()

    # --- Step 5: Optimize geometries ---
    print(">>> OPTIMIZING")
    print("-" * 40)
    optimized = []
    for f in all_features:
        try:
            optimized.append(round_coords(f, precision=3))
        except Exception:
            optimized.append(f)
    all_features = optimized
    print(f"  Rounded coordinates for {len(all_features):,} features")
    print()

    # --- Step 6: Export ---
    print(">>> EXPORTING")
    print("-" * 40)

    by_type = split_by_type(all_features)

    file_groups = {}
    for dtype, features in by_type.items():
        filename = TYPE_TO_FILENAME.get(dtype, f'{dtype}.geojson')
        if filename not in file_groups:
            file_groups[filename] = []
        file_groups[filename].extend(features)

    for filename, features in sorted(file_groups.items()):
        filepath = os.path.join(output_dir, filename)
        try:
            save_geojson(features, filepath)
            print(f"  {filename}: {len(features):,} features")
        except Exception as exc:
            print(f"  {filename}: FAILED ({exc})")

    all_path = os.path.join(output_dir, 'all_disasters.geojson')
    try:
        save_geojson(all_features, all_path)
        print(f"  all_disasters.geojson: {len(all_features):,} features")
    except Exception as exc:
        print(f"  all_disasters.geojson: FAILED ({exc})")

    compat_path = os.path.join(output_dir, 'disasters.geojson')
    try:
        save_geojson(all_features, compat_path)
        print(f"  disasters.geojson: {len(all_features):,} features (compat)")
    except Exception as exc:
        print(f"  disasters.geojson: FAILED ({exc})")

    meta_path = os.path.join(output_dir, 'metadata.json')
    try:
        save_metadata(all_features, meta_path)
        print(f"  metadata.json")
    except Exception as exc:
        print(f"  metadata.json: FAILED ({exc})")
    print()

    # --- Step 7: Summary ---
    elapsed = time.time() - start_time
    print("=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print()
    print(f"  Total features: {len(all_features):,}")
    print(f"  Time elapsed:   {elapsed:.1f}s")
    print()

    if by_type:
        print("  By type:")
        for dtype in sorted(by_type.keys()):
            print(f"    {dtype}: {len(by_type[dtype]):,}")
        print()

    if source_counts:
        print("  By source:")
        for source in sorted(source_counts.keys()):
            print(f"    {source}: {source_counts[source]:,}")
        print()

    print(f"  Output directory: {os.path.abspath(output_dir)}")
    print()


if __name__ == '__main__':
    main()
