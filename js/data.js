/**
 * Data module — loads, stores, and filters disaster GeoJSON data.
 * Supports two loading modes:
 *   1. Per-type files (earthquakes.geojson, hurricanes.geojson, etc.)
 *   2. Single combined file (disasters.geojson) as fallback
 */

const DataModule = (() => {
  let _allFeatures = [];
  let _filteredFeatures = [];
  let _metadata = null;
  let _loadedTypes = new Set();

  const DISASTER_TYPES = [
    { key: 'earthquake',        label: 'Earthquakes',        color: '#1a1a1a' },
    { key: 'hurricane',         label: 'Hurricanes',         color: '#1565c0' },
    { key: 'wildfire',          label: 'Wildfires',          color: '#d32f2f' },
    { key: 'drought',           label: 'Droughts',           color: '#f9a825' },
    { key: 'flooding',          label: 'Flooding',           color: '#2e7d32' },
    { key: 'volcanic_eruption', label: 'Volcanic Eruptions', color: '#7b1fa2' },
    { key: 'tsunami',           label: 'Tsunamis',           color: '#0d47a1' },
    { key: 'tornado',           label: 'Tornadoes',          color: '#757575' },
    { key: 'ice_storm',         label: 'Ice Storms',         color: '#b0bec5' },
    { key: 'blizzard',          label: 'Blizzards',          color: '#cfd8dc' },
    { key: 'cold_wave',         label: 'Cold Waves',         color: '#90a4ae' },
    { key: 'heatwave',          label: 'Heatwaves',          color: '#ef6c00' }
  ];

  const TYPE_TO_FILE = {
    earthquake:        'data/earthquakes.geojson',
    hurricane:         'data/hurricanes.geojson',
    wildfire:          'data/wildfires.geojson',
    drought:           'data/droughts.geojson',
    flooding:          'data/floods.geojson',
    volcanic_eruption: 'data/volcanoes.geojson',
    tsunami:           'data/tsunamis.geojson',
    tornado:           'data/tornadoes.geojson',
    ice_storm:         'data/winter.geojson',
    blizzard:          'data/winter.geojson',
    cold_wave:         'data/winter.geojson',
    heatwave:          'data/heatwaves.geojson'
  };

  const DEFAULT_ENABLED_TYPES = DISASTER_TYPES.map(t => t.key);

  function getColorForType(type) {
    const found = DISASTER_TYPES.find(t => t.key === type);
    return found ? found.color : '#888';
  }

  /**
   * Try to load metadata.json first, then per-type files, falling back to combined file.
   */
  async function load() {
    _metadata = await _tryLoadMetadata();

    const perTypeLoaded = await _tryLoadPerType();
    if (!perTypeLoaded) {
      await _loadCombined();
    }

    return _allFeatures;
  }

  async function _tryLoadMetadata() {
    try {
      const resp = await fetch('data/metadata.json');
      if (resp.ok) return await resp.json();
    } catch (e) { /* ignore */ }
    return null;
  }

  async function _tryLoadPerType() {
    const uniqueFiles = [...new Set(Object.values(TYPE_TO_FILE))];
    const results = await Promise.allSettled(
      uniqueFiles.map(url => fetch(url).then(r => r.ok ? r.json() : Promise.reject()))
    );

    let anyLoaded = false;
    for (let i = 0; i < uniqueFiles.length; i++) {
      if (results[i].status === 'fulfilled') {
        const geojson = results[i].value;
        const features = geojson.features || [];
        _allFeatures.push(...features);
        anyLoaded = true;
      }
    }

    if (anyLoaded) {
      _deduplicateById();
      DISASTER_TYPES.forEach(t => _loadedTypes.add(t.key));
    }

    return anyLoaded;
  }

  async function _loadCombined() {
    const urls = ['data/all_disasters.geojson', 'data/disasters.geojson'];
    for (const url of urls) {
      try {
        const resp = await fetch(url);
        if (!resp.ok) continue;
        const geojson = await resp.json();
        _allFeatures = geojson.features || [];
        DISASTER_TYPES.forEach(t => _loadedTypes.add(t.key));
        return;
      } catch (e) { /* try next */ }
    }
    throw new Error('No disaster data files found');
  }

  function _deduplicateById() {
    const seen = new Set();
    _allFeatures = _allFeatures.filter(f => {
      const id = f.properties && f.properties.id;
      if (!id || seen.has(id)) return false;
      seen.add(id);
      return true;
    });
  }

  /**
   * Lazy-load a specific disaster type's file on demand.
   */
  async function loadType(typeKey) {
    if (_loadedTypes.has(typeKey)) return;
    const file = TYPE_TO_FILE[typeKey];
    if (!file) return;

    try {
      const resp = await fetch(file);
      if (!resp.ok) return;
      const geojson = await resp.json();
      const features = geojson.features || [];
      _allFeatures.push(...features);
      _deduplicateById();
      _loadedTypes.add(typeKey);
    } catch (e) {
      console.warn(`Failed to load ${file}:`, e);
    }
  }

  function getMetadata() {
    return _metadata;
  }

  function getAllFeatures() {
    return _allFeatures;
  }

  function getFilteredFeatures() {
    return _filteredFeatures;
  }

  function getYearRange() {
    if (_metadata && _metadata.min_year && _metadata.max_year) {
      return { min: _metadata.min_year, max: _metadata.max_year };
    }
    if (!_allFeatures.length) return { min: 1976, max: new Date().getFullYear() };
    let min = Infinity, max = -Infinity;
    for (const f of _allFeatures) {
      const y = f.properties.year;
      if (y < min) min = y;
      if (y > max) max = y;
    }
    return { min, max };
  }

  function filter({ enabledTypes, yearStart, yearEnd }) {
    _filteredFeatures = _allFeatures.filter(f => {
      const p = f.properties;
      if (!enabledTypes.includes(p.type)) return false;
      if (p.year < yearStart || p.year > yearEnd) return false;
      return true;
    });
    return _filteredFeatures;
  }

  function search(query) {
    if (!query || !query.trim()) return [];
    const q = query.trim().toLowerCase();
    return _allFeatures.filter(f => {
      const p = f.properties;
      return (
        (p.name && p.name.toLowerCase().includes(q)) ||
        (p.country && p.country.toLowerCase().includes(q)) ||
        (p.region && p.region.toLowerCase().includes(q)) ||
        (String(p.year).includes(q)) ||
        (p.type && p.type.replace(/_/g, ' ').includes(q))
      );
    });
  }

  function countByType(yearStart, yearEnd) {
    const counts = {};
    for (const t of DISASTER_TYPES) counts[t.key] = 0;
    for (const f of _allFeatures) {
      const p = f.properties;
      if (p.year >= yearStart && p.year <= yearEnd) {
        counts[p.type] = (counts[p.type] || 0) + 1;
      }
    }
    return counts;
  }

  function getUniqueEvents(features) {
    const seen = new Set();
    return features.filter(f => {
      const baseId = (f.properties.id || '').replace(/_area$/, '').replace(/_ring$/, '');
      if (seen.has(baseId)) return false;
      seen.add(baseId);
      return true;
    });
  }

  function exportFiltered() {
    const geojson = {
      type: 'FeatureCollection',
      features: _filteredFeatures
    };
    const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'filtered_disasters.geojson';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return {
    DISASTER_TYPES,
    DEFAULT_ENABLED_TYPES,
    getColorForType,
    load,
    loadType,
    getMetadata,
    getAllFeatures,
    getFilteredFeatures,
    getYearRange,
    filter,
    search,
    countByType,
    getUniqueEvents,
    exportFiltered
  };
})();
