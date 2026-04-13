/**
 * Map module — initializes Leaflet, manages layers and visualizations.
 */

const MapModule = (() => {
  let _map = null;
  let _layerGroups = {};   // keyed by disaster type
  let _allLayers = [];     // flat list of {layer, feature} for fitBounds etc.
  let _baseLayers = {};
  let _currentBase = 'dark';

  const TILE_URLS = {
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
  };

  const TILE_ATTR = '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>';

  function init(containerId) {
    _map = L.map(containerId, {
      center: [20, 0],
      zoom: 3,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: true,
      attributionControl: true,
      worldCopyJump: true
    });

    for (const [name, url] of Object.entries(TILE_URLS)) {
      _baseLayers[name] = L.tileLayer(url, {
        attribution: TILE_ATTR,
        maxZoom: 18,
        subdomains: 'abcd'
      });
    }

    _baseLayers.dark.addTo(_map);

    for (const t of DataModule.DISASTER_TYPES) {
      _layerGroups[t.key] = L.layerGroup().addTo(_map);
    }

    window.addEventListener('resize', () => _map.invalidateSize());
    window.addEventListener('orientationchange', () => {
      setTimeout(() => _map.invalidateSize(), 200);
    });

    return _map;
  }

  function getMap() {
    return _map;
  }

  function switchBase(name) {
    if (!_baseLayers[name] || name === _currentBase) return;
    _map.removeLayer(_baseLayers[_currentBase]);
    _baseLayers[name].addTo(_map);
    _currentBase = name;

    const tilePane = document.querySelector('.leaflet-tile-pane');
    if (tilePane) {
      tilePane.style.filter = name === 'dark'
        ? 'brightness(0.85) contrast(1.1) saturate(0.8)'
        : name === 'satellite'
          ? 'none'
          : 'brightness(0.95) contrast(1.05)';
    }
  }

  function getCurrentBase() {
    return _currentBase;
  }

  /**
   * Render a set of GeoJSON features onto the map.
   * Clears existing layers first.
   */
  function renderFeatures(features) {
    clearAll();
    _allLayers = [];

    for (const feature of features) {
      const type = feature.properties.type;
      const group = _layerGroups[type];
      if (!group) continue;

      const layer = createLayer(feature);
      if (layer) {
        layer.addTo(group);
        _allLayers.push({ layer, feature });
      }
    }
  }

  function clearAll() {
    for (const group of Object.values(_layerGroups)) {
      group.clearLayers();
    }
    _allLayers = [];
  }

  /**
   * Create appropriate Leaflet layer for a feature based on type + geometry.
   */
  function createLayer(feature) {
    const props = feature.properties;
    const geomType = feature.geometry.type;
    const color = DataModule.getColorForType(props.type);
    const isArea = props._role === 'area';

    let layer;

    if (geomType === 'Point') {
      layer = createPointLayer(feature, color);
    } else if (geomType === 'Polygon' || geomType === 'MultiPolygon') {
      layer = createPolygonLayer(feature, color, isArea);
    } else if (geomType === 'LineString' || geomType === 'MultiLineString') {
      layer = createLineLayer(feature, color);
    }

    if (layer) {
      layer.bindPopup(() => buildPopup(props), {
        maxWidth: 340,
        className: 'disaster-popup'
      });
    }

    return layer;
  }

  function createPointLayer(feature, color) {
    const coords = feature.geometry.coordinates;
    const props = feature.properties;
    const latlng = [coords[1], coords[0]];

    let radius = 6;
    if (props.type === 'earthquake' && props.magnitude) {
      radius = Math.max(5, Math.min(20, props.magnitude * 2));
    }

    return L.circleMarker(latlng, {
      radius: radius,
      fillColor: color,
      fillOpacity: 0.8,
      color: color,
      weight: 2,
      opacity: 1
    });
  }

  function createPolygonLayer(feature, color, isArea) {
    return L.geoJSON(feature, {
      style: {
        color: color,
        weight: isArea ? 1.5 : 2,
        opacity: isArea ? 0.6 : 0.8,
        fillColor: color,
        fillOpacity: isArea ? 0.1 : 0.15,
        dashArray: isArea ? '4 4' : null
      }
    });
  }

  function createLineLayer(feature, color) {
    return L.geoJSON(feature, {
      style: {
        color: color,
        weight: 3,
        opacity: 0.8,
        dashArray: null,
        lineCap: 'round',
        lineJoin: 'round'
      }
    });
  }

  function buildPopup(props) {
    const color = DataModule.getColorForType(props.type);
    const typeName = props.type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

    let metaHtml = '';

    const addMeta = (label, value) => {
      if (value !== undefined && value !== null && value !== '') {
        metaHtml += `<div class="popup-meta-item"><span class="popup-meta-label">${label}: </span><span class="popup-meta-value">${value}</span></div>`;
      }
    };

    addMeta('Year', props.year);
    addMeta('Region', props.region || props.country);
    addMeta('Type', typeName);

    if (props.type === 'earthquake') {
      addMeta('Magnitude', props.severity);
    } else if (props.type === 'hurricane') {
      addMeta('Category', props.severity);
      addMeta('Max Wind', props.maxWind);
    } else {
      addMeta('Severity', props.severity);
    }

    addMeta('Deaths', props.deaths !== undefined ? props.deaths.toLocaleString() : null);

    return `
      <div class="popup-content">
        <div class="popup-header">
          <span class="popup-type-dot" style="background:${color}"></span>
          <span class="popup-title">${props.name}</span>
        </div>
        <div class="popup-meta">${metaHtml}</div>
        ${props.description ? `<div class="popup-description">${props.description}</div>` : ''}
        ${props.source ? `<div class="popup-source">Source: ${props.source}</div>` : ''}
      </div>
    `;
  }

  /**
   * Fit the map view to encompass all currently visible layers.
   */
  function fitToVisible() {
    if (!_allLayers.length) return;

    const bounds = L.latLngBounds();
    for (const { layer } of _allLayers) {
      if (layer.getBounds) {
        bounds.extend(layer.getBounds());
      } else if (layer.getLatLng) {
        bounds.extend(layer.getLatLng());
      }
    }

    if (bounds.isValid()) {
      _map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
    }
  }

  /**
   * Fly to a specific feature on the map.
   */
  function flyToFeature(feature) {
    const geom = feature.geometry;
    if (geom.type === 'Point') {
      _map.flyTo([geom.coordinates[1], geom.coordinates[0]], 8, { duration: 1 });
    } else {
      const tempLayer = L.geoJSON(feature);
      const bounds = tempLayer.getBounds();
      if (bounds.isValid()) {
        _map.flyToBounds(bounds, { padding: [50, 50], maxZoom: 10, duration: 1 });
      }
    }

    // Open popup for the matching layer
    setTimeout(() => {
      for (const { layer, feature: f } of _allLayers) {
        if (f.properties.id === feature.properties.id) {
          if (layer.openPopup) layer.openPopup();
          break;
        }
      }
    }, 1100);
  }

  return {
    init,
    getMap,
    switchBase,
    getCurrentBase,
    renderFeatures,
    clearAll,
    fitToVisible,
    flyToFeature
  };
})();
