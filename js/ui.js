/**
 * UI module — builds and manages all UI panels: filters, timeline, search, legend, toolbar.
 */

const UIModule = (() => {
  let _enabledTypes = [];
  let _yearStart = 0;
  let _yearEnd = 0;
  let _dataRange = { min: 0, max: 0 };
  let _onChange = null;        // callback when filters/timeline change
  let _playbackInterval = null;
  let _searchDebounce = null;

  function init(onChange) {
    _onChange = onChange;
    _dataRange = DataModule.getYearRange();

    const currentYear = new Date().getFullYear();
    _yearStart = currentYear - 50;
    _yearEnd = currentYear;
    _enabledTypes = [...DataModule.DEFAULT_ENABLED_TYPES];

    buildFilterPanel();
    buildTimeline();
    buildSearch();
    buildLegend();
    buildToolbar();
    updateCounter();
  }

  /* ──────────── Filter Panel ──────────── */

  function buildFilterPanel() {
    const panel = document.getElementById('filter-panel');
    const toggle = document.getElementById('filter-toggle');

    let html = '<div class="filter-heading">Disaster Types</div><div class="filter-group" id="filter-checks">';

    for (const t of DataModule.DISASTER_TYPES) {
      const checked = _enabledTypes.includes(t.key) ? 'checked' : '';
      html += `
        <label class="filter-item" data-type="${t.key}">
          <input type="checkbox" value="${t.key}" ${checked}>
          <span class="filter-dot" style="color:${t.color}"></span>
          <span class="filter-label">${t.label}</span>
          <span class="filter-count" id="count-${t.key}">0</span>
        </label>`;
    }

    html += '</div>';
    html += `
      <div class="filter-actions">
        <button class="filter-btn" id="btn-select-all">Select All</button>
        <button class="filter-btn" id="btn-clear-all">Clear All</button>
        <button class="filter-btn" id="btn-reset">Reset</button>
      </div>`;

    panel.innerHTML = html;

    panel.addEventListener('change', (e) => {
      if (e.target.type === 'checkbox') {
        syncEnabledTypes();
        fireChange();
      }
    });

    document.getElementById('btn-select-all').addEventListener('click', () => {
      panel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
      syncEnabledTypes();
      fireChange();
    });

    document.getElementById('btn-clear-all').addEventListener('click', () => {
      panel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
      syncEnabledTypes();
      fireChange();
    });

    document.getElementById('btn-reset').addEventListener('click', () => {
      const currentYear = new Date().getFullYear();
      _yearStart = currentYear - 50;
      _yearEnd = currentYear;
      _enabledTypes = [...DataModule.DEFAULT_ENABLED_TYPES];
      panel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
      document.getElementById('year-start').value = _yearStart;
      document.getElementById('year-end').value = _yearEnd;
      updateSlider();
      fireChange();
    });

    // Toggle collapse
    toggle.addEventListener('click', () => {
      panel.classList.toggle('collapsed');
      toggle.classList.toggle('shifted');
      toggle.textContent = panel.classList.contains('collapsed') ? '☰ Filters' : '✕';
    });

    toggle.textContent = '✕';
    toggle.classList.add('shifted');
  }

  function syncEnabledTypes() {
    const checks = document.querySelectorAll('#filter-checks input[type="checkbox"]');
    _enabledTypes = [];
    checks.forEach(cb => {
      if (cb.checked) _enabledTypes.push(cb.value);
    });
  }

  function updateFilterCounts() {
    const counts = DataModule.countByType(_yearStart, _yearEnd);
    for (const [type, count] of Object.entries(counts)) {
      const el = document.getElementById(`count-${type}`);
      if (el) el.textContent = count;
    }
  }

  /* ──────────── Timeline ──────────── */

  function buildTimeline() {
    const startInput = document.getElementById('year-start');
    const endInput = document.getElementById('year-end');
    const slider = document.getElementById('timeline-slider');

    startInput.value = _yearStart;
    endInput.value = _yearEnd;
    slider.min = _dataRange.min;
    slider.max = _dataRange.max;
    slider.value = _yearEnd;

    startInput.addEventListener('change', () => {
      const val = parseInt(startInput.value, 10);
      if (!isNaN(val)) {
        _yearStart = Math.max(_dataRange.min, Math.min(val, _yearEnd));
        startInput.value = _yearStart;
        fireChange();
      }
    });

    endInput.addEventListener('change', () => {
      const val = parseInt(endInput.value, 10);
      if (!isNaN(val)) {
        _yearEnd = Math.min(_dataRange.max, Math.max(val, _yearStart));
        endInput.value = _yearEnd;
        slider.value = _yearEnd;
        fireChange();
      }
    });

    slider.addEventListener('input', () => {
      _yearEnd = parseInt(slider.value, 10);
      endInput.value = _yearEnd;
      fireChange();
    });

    // Quick buttons
    document.querySelectorAll('.timeline-quick-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const range = btn.dataset.range;
        const currentYear = new Date().getFullYear();
        document.querySelectorAll('.timeline-quick-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        if (range === 'all') {
          _yearStart = _dataRange.min;
          _yearEnd = _dataRange.max;
        } else {
          const years = parseInt(range, 10);
          _yearStart = currentYear - years;
          _yearEnd = currentYear;
        }

        document.getElementById('year-start').value = _yearStart;
        document.getElementById('year-end').value = _yearEnd;
        slider.value = _yearEnd;
        fireChange();
      });
    });

    // Playback
    const playBtn = document.getElementById('btn-play');
    playBtn.addEventListener('click', () => {
      if (_playbackInterval) {
        stopPlayback();
      } else {
        startPlayback();
      }
    });
  }

  function updateSlider() {
    const slider = document.getElementById('timeline-slider');
    if (slider) slider.value = _yearEnd;
  }

  function startPlayback() {
    const btn = document.getElementById('btn-play');
    btn.classList.add('active');
    btn.textContent = '⏸';

    _yearStart = _dataRange.min;
    _yearEnd = _dataRange.min;
    document.getElementById('year-start').value = _yearStart;

    _playbackInterval = setInterval(() => {
      _yearEnd += 1;
      if (_yearEnd > _dataRange.max) {
        stopPlayback();
        return;
      }
      document.getElementById('year-end').value = _yearEnd;
      document.getElementById('timeline-slider').value = _yearEnd;
      fireChange();
    }, 200);
  }

  function stopPlayback() {
    if (_playbackInterval) {
      clearInterval(_playbackInterval);
      _playbackInterval = null;
    }
    const btn = document.getElementById('btn-play');
    btn.classList.remove('active');
    btn.textContent = '▶';
  }

  /* ──────────── Search ──────────── */

  function buildSearch() {
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');

    input.addEventListener('input', () => {
      clearTimeout(_searchDebounce);
      _searchDebounce = setTimeout(() => {
        const query = input.value;
        if (!query.trim()) {
          results.classList.remove('active');
          results.innerHTML = '';
          return;
        }

        const matches = DataModule.search(query);
        const unique = DataModule.getUniqueEvents(matches);
        if (!unique.length) {
          results.innerHTML = '<div class="search-result-item"><span class="search-result-name" style="color:var(--text-muted)">No results found</span></div>';
          results.classList.add('active');
          return;
        }

        results.innerHTML = unique.slice(0, 20).map(f => {
          const p = f.properties;
          const color = DataModule.getColorForType(p.type);
          return `<div class="search-result-item" data-id="${p.id}">
            <div class="search-result-name"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px;vertical-align:middle;"></span>${p.name}</div>
            <div class="search-result-meta">${p.year} · ${p.country}</div>
          </div>`;
        }).join('');

        results.classList.add('active');
      }, 150);
    });

    results.addEventListener('click', (e) => {
      const item = e.target.closest('.search-result-item');
      if (!item || !item.dataset.id) return;

      const feature = DataModule.getAllFeatures().find(f => f.properties.id === item.dataset.id);
      if (feature) {
        MapModule.flyToFeature(feature);
      }
      results.classList.remove('active');
      input.value = '';
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('#search-container')) {
        results.classList.remove('active');
      }
    });
  }

  /* ──────────── Legend ──────────── */

  function buildLegend() {
    const container = document.getElementById('legend-items');
    let html = '';

    const symbolMap = {
      earthquake: 'circle',
      hurricane: 'line',
      wildfire: 'circle',
      drought: 'polygon',
      flooding: 'polygon',
      volcanic_eruption: 'circle',
      tsunami: 'line',
      tornado: 'line',
      ice_storm: 'polygon',
      blizzard: 'polygon',
      cold_wave: 'polygon',
      heatwave: 'polygon'
    };

    for (const t of DataModule.DISASTER_TYPES) {
      const sym = symbolMap[t.key] || 'circle';
      let symbolClass = 'legend-symbol';
      let style = '';

      if (sym === 'line') {
        symbolClass += ' line';
        style = `background:${t.color}`;
      } else if (sym === 'polygon') {
        symbolClass += ' polygon';
        style = `border-color:${t.color}`;
      } else {
        style = `background:${t.color}`;
      }

      html += `<div class="legend-item"><span class="${symbolClass}" style="${style}"></span>${t.label}</div>`;
    }

    container.innerHTML = html;
  }

  /* ──────────── Toolbar ──────────── */

  function buildToolbar() {
    const btnFit = document.getElementById('btn-fit');
    const btnExport = document.getElementById('btn-export');
    const btnTheme = document.getElementById('btn-theme');

    btnFit.addEventListener('click', () => MapModule.fitToVisible());
    btnExport.addEventListener('click', () => DataModule.exportFiltered());

    btnTheme.addEventListener('click', () => {
      const bases = ['dark', 'light', 'satellite'];
      const current = MapModule.getCurrentBase();
      const idx = bases.indexOf(current);
      const next = bases[(idx + 1) % bases.length];
      MapModule.switchBase(next);
      btnTheme.title = `Theme: ${next}`;
    });
  }

  /* ──────────── Counter ──────────── */

  function updateCounter() {
    const el = document.getElementById('event-counter');
    const filtered = DataModule.getFilteredFeatures();
    const unique = DataModule.getUniqueEvents(filtered);
    el.textContent = `${unique.length} events visible`;
  }

  /* ──────────── Helpers ──────────── */

  function getState() {
    return {
      enabledTypes: _enabledTypes,
      yearStart: _yearStart,
      yearEnd: _yearEnd
    };
  }

  function fireChange() {
    updateFilterCounts();
    if (_onChange) _onChange(getState());
    updateCounter();
  }

  /**
   * Called after initial data load to set counts and trigger first render.
   */
  function initialRender() {
    updateFilterCounts();
    updateCounter();
  }

  return {
    init,
    getState,
    updateCounter,
    updateFilterCounts,
    initialRender
  };
})();
