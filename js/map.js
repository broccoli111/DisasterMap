/**
 * Map module — initializes Leaflet, manages layers, and renders disaster features.
 */

import { DISASTER_TYPES, getFilteredFeatures } from './data.js';

let _map = null;
let _layerGroups = {};  // keyed by disaster type
let _allLayers = [];    // flat list of { layer, feature } for bounds fitting
let _baseLayers = {};
let _currentBase = 'dark';

const TILE_URLS = {
  dark:      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  light:     'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
};

const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';

function initMap(containerId) {
  _map = L.map(containerId, {
    center: [20, 0],
    zoom: 3,
    minZoom: 2,
    maxZoom: 18,
    zoomControl: true,
    worldCopyJump: true,
    preferCanvas: true
  });

  _map.zoomControl.setPosition('bottomright');

  for (const [name, url] of Object.entries(TILE_URLS)) {
    _baseLayers[name] = L.tileLayer(url, {
      attribution: TILE_ATTR,
      maxZoom: 18,
      subdomains: 'abcd'
    });
  }

  _baseLayers.dark.addTo(_map);

  for (const type of Object.keys(DISASTER_TYPES)) {
    _layerGroups[type] = L.layerGroup().addTo(_map);
  }

  return _map;
}

function getMap() {
  return _map;
}

function switchBaseLayer(name) {
  if (!_baseLayers[name] || name === _currentBase) return;
  _map.removeLayer(_baseLayers[_currentBase]);
  _baseLayers[name].addTo(_map);
  _currentBase = name;

  const tilePane = document.querySelector('.leaflet-tile-pane');
  if (tilePane) {
    tilePane.style.filter = name === 'dark'
      ? 'brightness(0.7) contrast(1.1) saturate(0.3)'
      : name === 'satellite'
        ? 'none'
        : 'brightness(0.85) contrast(1.05) saturate(0.6)';
  }
}

function getCurrentBase() {
  return _currentBase;
}

function refreshLayers() {
  _allLayers = [];
  for (const type of Object.keys(DISASTER_TYPES)) {
    _layerGroups[type].clearLayers();
  }

  const features = getFilteredFeatures();

  for (const feature of features) {
    const props = feature.properties;
    const geom = feature.geometry;
    const type = props.type;
    const color = DISASTER_TYPES[type]?.color || '#888';
    const group = _layerGroups[type];
    if (!group) continue;

    let layer = null;

    switch (geom.type) {
      case 'Point':
        layer = createPointLayer(feature, color, type);
        break;
      case 'LineString':
      case 'MultiLineString':
        layer = createLineLayer(feature, color, type);
        break;
      case 'Polygon':
      case 'MultiPolygon':
        layer = createPolygonLayer(feature, color, type);
        break;
    }

    if (layer) {
      layer.bindPopup(() => buildPopupHTML(props, type), { maxWidth: 320, className: '' });
      group.addLayer(layer);
      _allLayers.push({ layer, feature });
    }
  }
}

function createPointLayer(feature, color, type) {
  const coords = feature.geometry.coordinates;
  const latlng = [coords[1], coords[0]];

  const circleOpts = {
    radius: 6,
    fillColor: color,
    fillOpacity: 0.9,
    color: lightenColor(color, 40),
    weight: 2,
    opacity: 0.8
  };

  if (type === 'earthquake') {
    circleOpts.fillColor = '#111';
    circleOpts.color = '#444';
  } else if (type === 'wildfire') {
    circleOpts.fillColor = '#d32f2f';
    circleOpts.color = '#ff5252';
  } else if (type === 'volcanic_eruption') {
    circleOpts.fillColor = '#7b1fa2';
    circleOpts.color = '#ba68c8';
  }

  return L.circleMarker(latlng, circleOpts);
}

function createLineLayer(feature, color, type) {
  const coords = feature.geometry.type === 'MultiLineString'
    ? feature.geometry.coordinates.map(line => line.map(c => [c[1], c[0]]))
    : [feature.geometry.coordinates.map(c => [c[1], c[0]])];

  const lineOpts = {
    color: color,
    weight: 3,
    opacity: 0.8,
    dashArray: null,
    lineCap: 'round',
    lineJoin: 'round'
  };

  if (type === 'hurricane') {
    lineOpts.weight = 3;
    lineOpts.dashArray = '8, 4';
  } else if (type === 'tornado') {
    lineOpts.color = '#757575';
    lineOpts.weight = 3;
  } else if (type === 'tsunami') {
    lineOpts.color = '#0d47a1';
    lineOpts.weight = 3;
    lineOpts.dashArray = '6, 6';
  }

  return feature.geometry.type === 'MultiLineString'
    ? L.polyline(coords, lineOpts)
    : L.polyline(coords[0], lineOpts);
}

function createPolygonLayer(feature, color, type) {
  const coords = feature.geometry.type === 'MultiPolygon'
    ? feature.geometry.coordinates.map(poly => poly.map(ring => ring.map(c => [c[1], c[0]])))
    : [feature.geometry.coordinates.map(ring => ring.map(c => [c[1], c[0]]))];

  const polyOpts = {
    color: color,
    weight: 2,
    opacity: 0.7,
    fillColor: color,
    fillOpacity: 0.12,
    dashArray: null
  };

  if (type === 'earthquake') {
    polyOpts.color = '#444';
    polyOpts.fillColor = '#111';
    polyOpts.fillOpacity = 0.08;
  } else if (type === 'ice_storm' || type === 'blizzard' || type === 'cold_wave') {
    polyOpts.fillOpacity = 0.08;
    polyOpts.dashArray = '4, 4';
  }

  if (feature.geometry.type === 'MultiPolygon') {
    const latLngs = coords.map(poly => poly);
    return L.polygon(latLngs, polyOpts);
  }
  return L.polygon(coords[0], polyOpts);
}

function buildPopupHTML(props, type) {
  const typeInfo = DISASTER_TYPES[type] || { label: type, color: '#888' };
  const deaths = props.deaths != null ? Number(props.deaths).toLocaleString() : 'Unknown';

  let metaRows = '';
  metaRows += metaRow('Region', props.region || props.country);
  metaRows += metaRow('Country', props.country);
  metaRows += metaRow('Severity', props.severity);
  if (props.maxWind) metaRows += metaRow('Max Wind', props.maxWind);
  metaRows += metaRow('Est. Deaths', deaths);

  return `
    <div class="popup-content">
      <span class="popup-type-badge" style="background:${typeInfo.color}">${typeInfo.label}</span>
      <h3>${escapeHTML(props.name)}</h3>
      <div class="popup-year">${props.year}</div>
      <div class="popup-meta">${metaRows}</div>
      <div class="popup-desc">${escapeHTML(props.description || '')}</div>
      <div class="popup-source">Source: ${escapeHTML(props.source || 'N/A')}</div>
    </div>
  `;
}

function metaRow(label, value) {
  if (!value) return '';
  return `<div class="popup-meta-row"><span class="label">${label}</span><span class="value">${escapeHTML(String(value))}</span></div>`;
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function lightenColor(hex, percent) {
  const num = parseInt(hex.replace('#', ''), 16);
  const r = Math.min(255, (num >> 16) + percent);
  const g = Math.min(255, ((num >> 8) & 0x00FF) + percent);
  const b = Math.min(255, (num & 0x0000FF) + percent);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

function fitToVisible() {
  if (_allLayers.length === 0) return;
  const group = L.featureGroup(_allLayers.map(l => l.layer));
  try {
    _map.fitBounds(group.getBounds().pad(0.1), { maxZoom: 10, animate: true });
  } catch (e) {
    // bounds might be invalid if all points are identical
  }
}

function flyToFeature(feature) {
  const geom = feature.geometry;
  let latlng;
  if (geom.type === 'Point') {
    latlng = [geom.coordinates[1], geom.coordinates[0]];
    _map.flyTo(latlng, 6, { duration: 1 });
  } else if (geom.type === 'LineString') {
    latlng = [geom.coordinates[0][1], geom.coordinates[0][0]];
    _map.flyTo(latlng, 5, { duration: 1 });
  } else if (geom.type === 'Polygon') {
    const ring = geom.coordinates[0];
    const latLngs = ring.map(c => [c[1], c[0]]);
    _map.flyToBounds(L.latLngBounds(latLngs).pad(0.2), { maxZoom: 8, duration: 1 });
  } else {
    _map.setView([20, 0], 3);
  }

  // Open popup of matching layer
  for (const { layer, feature: f } of _allLayers) {
    if (f.properties.id === feature.properties.id) {
      setTimeout(() => layer.openPopup(), 1100);
      break;
    }
  }
}

function getVisibleCount() {
  return _allLayers.length;
}

export {
  initMap,
  getMap,
  switchBaseLayer,
  getCurrentBase,
  refreshLayers,
  fitToVisible,
  flyToFeature,
  getVisibleCount
};
