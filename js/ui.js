/**
 * UI module — builds and manages all UI controls: filters, timeline, search, legend, toolbar.
 */

import {
  DISASTER_TYPES,
  DEFAULT_ENABLED_TYPES,
  setActiveTypes,
  getActiveTypes,
  setYearRange,
  getYearRange,
  getDataYearExtent,
  searchFeatures,
  exportFilteredJSON,
  applyFilters,
  getFilteredFeatures
} from './data.js';

import {
  refreshLayers,
  fitToVisible,
  flyToFeature,
  getVisibleCount,
  switchBaseLayer,
  getCurrentBase
} from './map.js';

let _playbackInterval = null;
let _onUpdate = null; // callback after every filter/timeline change

function initUI(onUpdate) {
  _onUpdate = onUpdate;
  buildFilterPanel();
  buildTimeline();
  buildLegend();
  buildToolbar();
  bindSearch();
}

/* ==================== FILTER PANEL ==================== */

function buildFilterPanel() {
  const panel = document.getElementById('filter-panel');
  const toggle = document.getElementById('filter-toggle');

  let html = `
    <div class="filter-header">
      <h3>Disaster Types</h3>
      <button class="filter-close" id="filter-close-btn" title="Close">&times;</button>
    </div>
  `;

  for (const [type, info] of Object.entries(DISASTER_TYPES)) {
    html += `
      <label class="filter-item" data-type="${type}">
        <input type="checkbox" value="${type}" checked>
        <span class="filter-swatch" style="background:${info.color}"></span>
        <span class="filter-label">${info.label}</span>
      </label>
    `;
  }

  html += `
    <div class="filter-actions">
      <button class="filter-btn" id="filter-select-all">Select All</button>
      <button class="filter-btn" id="filter-clear-all">Clear All</button>
      <button class="filter-btn" id="filter-reset">Reset</button>
    </div>
  `;

  panel.innerHTML = html;

  panel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', () => {
      const checked = [...panel.querySelectorAll('input[type="checkbox"]:checked')].map(c => c.value);
      setActiveTypes(checked);
      triggerUpdate();
    });
  });

  document.getElementById('filter-select-all').addEventListener('click', () => {
    panel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
    setActiveTypes(Object.keys(DISASTER_TYPES));
    triggerUpdate();
  });

  document.getElementById('filter-clear-all').addEventListener('click', () => {
    panel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
    setActiveTypes([]);
    triggerUpdate();
  });

  document.getElementById('filter-reset').addEventListener('click', () => {
    panel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.checked = DEFAULT_ENABLED_TYPES.includes(cb.value);
    });
    setActiveTypes(DEFAULT_ENABLED_TYPES);
    triggerUpdate();
  });

  document.getElementById('filter-close-btn').addEventListener('click', () => {
    panel.classList.add('collapsed');
    toggle.style.display = 'flex';
  });

  toggle.addEventListener('click', () => {
    panel.classList.remove('collapsed');
    toggle.style.display = 'none';
  });

  toggle.style.display = 'none';
}

/* ==================== TIMELINE ==================== */

function buildTimeline() {
  const extent = getDataYearExtent();
  const range = getYearRange();

  const startInput = document.getElementById('year-start');
  const endInput = document.getElementById('year-end');
  const slider = document.getElementById('timeline-slider');
  const allBtn = document.getElementById('timeline-all-btn');
  const last50Btn = document.getElementById('timeline-last50-btn');
  const playBtn = document.getElementById('playback-btn');

  startInput.min = extent.min;
  startInput.max = extent.max;
  startInput.value = range.start;

  endInput.min = extent.min;
  endInput.max = extent.max;
  endInput.value = range.end;

  slider.min = extent.min;
  slider.max = extent.max;
  slider.value = range.end;

  const updateFromInputs = () => {
    let s = parseInt(startInput.value) || extent.min;
    let e = parseInt(endInput.value) || extent.max;
    if (s > e) { const t = s; s = e; e = t; }
    startInput.value = s;
    endInput.value = e;
    setYearRange(s, e);
    triggerUpdate();
  };

  startInput.addEventListener('change', updateFromInputs);
  endInput.addEventListener('change', updateFromInputs);

  slider.addEventListener('input', () => {
    const val = parseInt(slider.value);
    endInput.value = val;
    setYearRange(parseInt(startInput.value) || extent.min, val);
    triggerUpdate();
  });

  allBtn.addEventListener('click', () => {
    startInput.value = extent.min;
    endInput.value = extent.max;
    slider.value = extent.max;
    setYearRange(extent.min, extent.max);
    allBtn.classList.add('active');
    last50Btn.classList.remove('active');
    triggerUpdate();
  });

  last50Btn.addEventListener('click', () => {
    const now = new Date().getFullYear();
    startInput.value = now - 50;
    endInput.value = now;
    slider.value = now;
    setYearRange(now - 50, now);
    last50Btn.classList.add('active');
    allBtn.classList.remove('active');
    triggerUpdate();
  });

  last50Btn.classList.add('active');

  playBtn.addEventListener('click', () => togglePlayback(startInput, endInput, slider, extent));
}

function togglePlayback(startInput, endInput, slider, extent) {
  const playBtn = document.getElementById('playback-btn');

  if (_playbackInterval) {
    clearInterval(_playbackInterval);
    _playbackInterval = null;
    playBtn.textContent = '▶';
    playBtn.classList.remove('active');
    return;
  }

  playBtn.textContent = '⏸';
  playBtn.classList.add('active');

  let year = parseInt(startInput.value) || extent.min;
  const endYear = parseInt(endInput.value) || extent.max;

  _playbackInterval = setInterval(() => {
    if (year > endYear) {
      clearInterval(_playbackInterval);
      _playbackInterval = null;
      playBtn.textContent = '▶';
      playBtn.classList.remove('active');
      return;
    }

    endInput.value = year;
    slider.value = year;
    setYearRange(parseInt(startInput.value), year);
    triggerUpdate();
    year++;
  }, 300);
}

/* ==================== LEGEND ==================== */

function buildLegend() {
  const panel = document.getElementById('legend-panel');
  let html = '<h4>Legend</h4>';

  const legendItems = [
    { type: 'earthquake',        icon: 'dot',     label: 'Earthquake (epicenter)' },
    { type: 'earthquake',        icon: 'polygon', label: 'Earthquake (area)' },
    { type: 'hurricane',         icon: 'line',    label: 'Hurricane (path)' },
    { type: 'wildfire',          icon: 'dot',     label: 'Wildfire (origin)' },
    { type: 'wildfire',          icon: 'polygon', label: 'Wildfire (area)' },
    { type: 'drought',           icon: 'polygon', label: 'Drought (region)' },
    { type: 'flooding',          icon: 'polygon', label: 'Flooding (region)' },
    { type: 'volcanic_eruption', icon: 'dot',     label: 'Volcanic Eruption' },
    { type: 'tsunami',           icon: 'line',    label: 'Tsunami (path)' },
    { type: 'tornado',           icon: 'line',    label: 'Tornado (path)' },
    { type: 'ice_storm',         icon: 'polygon', label: 'Ice Storm' },
    { type: 'blizzard',          icon: 'polygon', label: 'Blizzard' },
    { type: 'cold_wave',         icon: 'polygon', label: 'Cold Wave' },
    { type: 'heatwave',          icon: 'polygon', label: 'Heatwave' }
  ];

  for (const item of legendItems) {
    const color = DISASTER_TYPES[item.type]?.color || '#888';
    let iconClass = 'legend-icon';
    let style = `background:${color}`;

    if (item.icon === 'line') {
      iconClass += ' line';
    } else if (item.icon === 'polygon') {
      iconClass += ' polygon';
      style = `border-color:${color}`;
    }

    html += `<div class="legend-item"><span class="${iconClass}" style="${style}"></span><span class="legend-text">${item.label}</span></div>`;
  }

  panel.innerHTML = html;
}

/* ==================== SEARCH ==================== */

function bindSearch() {
  const input = document.getElementById('search-input');
  const resultsPanel = document.getElementById('search-results');
  let debounceTimer = null;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const q = input.value.trim();
      if (q.length < 2) {
        resultsPanel.classList.remove('visible');
        return;
      }
      const results = searchFeatures(q);
      renderSearchResults(results, resultsPanel);
    }, 200);
  });

  input.addEventListener('focus', () => {
    if (input.value.trim().length >= 2) {
      const results = searchFeatures(input.value.trim());
      renderSearchResults(results, resultsPanel);
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('#search-container')) {
      resultsPanel.classList.remove('visible');
    }
  });
}

function renderSearchResults(features, container) {
  if (features.length === 0) {
    container.innerHTML = '<div class="search-result-item"><span class="result-name" style="color:var(--text-muted)">No results found</span></div>';
    container.classList.add('visible');
    return;
  }

  container.innerHTML = features.slice(0, 20).map(f => {
    const p = f.properties;
    const typeLabel = DISASTER_TYPES[p.type]?.label || p.type;
    return `
      <div class="search-result-item" data-id="${p.id}">
        <div class="result-name">${escapeHTML(p.name)}</div>
        <div class="result-meta">${p.year} · ${typeLabel} · ${p.country}</div>
      </div>
    `;
  }).join('');

  container.classList.add('visible');

  container.querySelectorAll('.search-result-item').forEach(item => {
    item.addEventListener('click', () => {
      const id = item.dataset.id;
      const feature = features.find(f => f.properties.id === id);
      if (feature) {
        flyToFeature(feature);
        container.classList.remove('visible');
      }
    });
  });
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ==================== TOOLBAR ==================== */

function buildToolbar() {
  const fitBtn = document.getElementById('tool-fit');
  const exportBtn = document.getElementById('tool-export');
  const themeBtn = document.getElementById('tool-theme');

  fitBtn.addEventListener('click', fitToVisible);

  exportBtn.addEventListener('click', exportFilteredJSON);

  themeBtn.addEventListener('click', () => {
    const bases = ['dark', 'light', 'satellite'];
    const current = getCurrentBase();
    const idx = bases.indexOf(current);
    const next = bases[(idx + 1) % bases.length];
    switchBaseLayer(next);
    themeBtn.title = `Theme: ${next}`;
  });
}

/* ==================== UPDATE CYCLE ==================== */

function triggerUpdate() {
  refreshLayers();
  updateCounter();
  if (_onUpdate) _onUpdate();
}

function updateCounter() {
  const el = document.getElementById('event-counter');
  const count = getVisibleCount();
  el.textContent = `${count} event${count !== 1 ? 's' : ''} visible`;
}

export { initUI, triggerUpdate, updateCounter };
