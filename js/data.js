/**
 * Data module — loads, stores, and filters disaster GeoJSON data.
 */

const DataModule = (() => {
  let _allFeatures = [];
  let _filteredFeatures = [];

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

  const DEFAULT_ENABLED_TYPES = DISASTER_TYPES.map(t => t.key);

  function getColorForType(type) {
    const found = DISASTER_TYPES.find(t => t.key === type);
    return found ? found.color : '#888';
  }

  async function load(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Failed to load data: ${resp.status}`);
    const geojson = await resp.json();
    _allFeatures = geojson.features || [];
    return _allFeatures;
  }

  function getAllFeatures() {
    return _allFeatures;
  }

  function getFilteredFeatures() {
    return _filteredFeatures;
  }

  /**
   * Returns the min and max year across the full dataset.
   */
  function getYearRange() {
    if (!_allFeatures.length) return { min: 1900, max: new Date().getFullYear() };
    let min = Infinity, max = -Infinity;
    for (const f of _allFeatures) {
      const y = f.properties.year;
      if (y < min) min = y;
      if (y > max) max = y;
    }
    return { min, max };
  }

  /**
   * Filter features by active types and year range.
   * Returns a new array (does not mutate _allFeatures).
   */
  function filter({ enabledTypes, yearStart, yearEnd }) {
    _filteredFeatures = _allFeatures.filter(f => {
      const p = f.properties;
      if (!enabledTypes.includes(p.type)) return false;
      if (p.year < yearStart || p.year > yearEnd) return false;
      return true;
    });
    return _filteredFeatures;
  }

  /**
   * Search features by query string (matches name, country, year, type).
   */
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

  /**
   * Count features per type within a year range.
   */
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

  /**
   * Deduplicate features by base id (removes _area suffix duplicates for listing).
   */
  function getUniqueEvents(features) {
    const seen = new Set();
    return features.filter(f => {
      const baseId = f.properties.id.replace(/_area$/, '');
      if (seen.has(baseId)) return false;
      seen.add(baseId);
      return true;
    });
  }

  /**
   * Export filtered features as downloadable JSON.
   */
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
