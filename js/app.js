/**
 * App module — bootstraps the application, wires modules together.
 */

(async function App() {
  const loadingOverlay = document.getElementById('loading-overlay');

  try {
    await DataModule.load('data/disasters.geojson');

    MapModule.init('map');

    UIModule.init((state) => {
      const features = DataModule.filter(state);
      MapModule.renderFeatures(features);
      UIModule.updateCounter();
    });

    // Trigger initial filter + render
    const initialState = UIModule.getState();
    const features = DataModule.filter(initialState);
    MapModule.renderFeatures(features);
    UIModule.initialRender();

    // Hide loading overlay
    if (loadingOverlay) {
      loadingOverlay.classList.add('hidden');
      setTimeout(() => loadingOverlay.remove(), 500);
    }
  } catch (err) {
    console.error('Failed to initialize application:', err);
    if (loadingOverlay) {
      loadingOverlay.querySelector('.loading-text').textContent =
        'Failed to load data. Make sure you are serving via HTTP (not file://).';
      loadingOverlay.querySelector('.loading-spinner').style.display = 'none';
    }
  }
})();
