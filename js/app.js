/**
 * App entry point — bootstraps data loading, map, and UI.
 */

import { loadData } from './data.js';
import { initMap, refreshLayers } from './map.js';
import { initUI, triggerUpdate, updateCounter } from './ui.js';

(async function main() {
  try {
    initMap('map');
    await loadData('data/disasters.geojson');
    initUI();
    triggerUpdate();

    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
      overlay.classList.add('fade-out');
      setTimeout(() => overlay.remove(), 500);
    }
  } catch (err) {
    console.error('Failed to initialize application:', err);
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
      overlay.innerHTML = `
        <div style="color:#ef5350;font-size:16px;text-align:center;padding:20px;">
          Failed to load disaster data.<br>
          <small style="color:#9aa0a6;">${err.message}</small>
        </div>
      `;
    }
  }
})();
