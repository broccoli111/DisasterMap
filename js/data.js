/**
 * Data module — loads, stores, and filters the GeoJSON disaster dataset.
 */

const DISASTER_TYPES = {
  earthquake:        { label: 'Earthquakes',        color: '#1a1a1a' },
  hurricane:         { label: 'Hurricanes',         color: '#1565c0' },
  wildfire:          { label: 'Wildfires',           color: '#d32f2f' },
  drought:           { label: 'Droughts',            color: '#f9a825' },
  flooding:          { label: 'Flooding',            color: '#2e7d32' },
  volcanic_eruption: { label: 'Volcanic Eruptions',  color: '#7b1fa2' },
  tsunami:           { label: 'Tsunamis',            color: '#0d47a1' },
  tornado:           { label: 'Tornadoes',           color: '#757575' },
  ice_storm:         { label: 'Ice Storms',          color: '#b0bec5' },
  blizzard:          { label: 'Blizzards',           color: '#cfd8dc' },
  cold_wave:         { label: 'Cold Waves',          color: '#90a4ae' },
  heatwave:          { label: 'Heatwaves',           color: '#e65100' }
};

const DEFAULT_ENABLED_TYPES = Object.keys(DISASTER_TYPES);

let _allFeatures = [];
let _filteredFeatures = [];
let _activeTypes = new Set(DEFAULT_ENABLED_TYPES);
let _yearRange = { start: new Date().getFullYear() - 50, end: new Date().getFullYear() };

async function loadData(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Failed to load data: ${resp.status}`);
  const geojson = await resp.json();
  _allFeatures = geojson.features || [];
  applyFilters();
  return _allFeatures;
}

function getAllFeatures() {
  return _allFeatures;
}

function getFilteredFeatures() {
  return _filteredFeatures;
}

function setActiveTypes(types) {
  _activeTypes = new Set(types);
  applyFilters();
}

function getActiveTypes() {
  return new Set(_activeTypes);
}

function setYearRange(start, end) {
  _yearRange = { start, end };
  applyFilters();
}

function getYearRange() {
  return { ..._yearRange };
}

function getDataYearExtent() {
  if (_allFeatures.length === 0) return { min: 1800, max: new Date().getFullYear() };
  let min = Infinity, max = -Infinity;
  for (const f of _allFeatures) {
    const y = f.properties.year;
    if (y < min) min = y;
    if (y > max) max = y;
  }
  return { min, max };
}

function applyFilters() {
  _filteredFeatures = _allFeatures.filter(f => {
    const p = f.properties;
    if (!_activeTypes.has(p.type)) return false;
    if (p.year < _yearRange.start || p.year > _yearRange.end) return false;
    return true;
  });
}

function searchFeatures(query) {
  if (!query || query.trim().length === 0) return [];
  const q = query.toLowerCase().trim();
  const seen = new Set();
  return _allFeatures.filter(f => {
    const p = f.properties;
    if (p._areaOf) return false; // skip area-only features in search
    if (seen.has(p.id)) return false;
    seen.add(p.id);
    const searchable = `${p.name} ${p.country} ${p.region} ${p.year} ${p.type}`.toLowerCase();
    return searchable.includes(q);
  });
}

function exportFilteredJSON() {
  const data = _filteredFeatures.map(f => f.properties);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'filtered_disasters.json';
  a.click();
  URL.revokeObjectURL(url);
}

export {
  DISASTER_TYPES,
  DEFAULT_ENABLED_TYPES,
  loadData,
  getAllFeatures,
  getFilteredFeatures,
  setActiveTypes,
  getActiveTypes,
  setYearRange,
  getYearRange,
  getDataYearExtent,
  applyFilters,
  searchFeatures,
  exportFilteredJSON
};
