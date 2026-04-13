/**
 * App module — bootstraps the application, wires modules together.
 */

(async function App() {
  const loadingOverlay = document.getElementById('loading-overlay');
  const loadingText = loadingOverlay && loadingOverlay.querySelector('.loading-text');

  try {
    if (loadingText) loadingText.textContent = 'Loading disaster data\u2026';

    await DataModule.load();

    const meta = DataModule.getMetadata();
    if (meta) {
      console.log(`Loaded ${meta.total_records} records (${meta.min_year}\u2013${meta.max_year})`);
    }

    MapModule.init('map');

    UIModule.init((state) => {
      const features = DataModule.filter(state);
      MapModule.renderFeatures(features);
      UIModule.updateCounter();
    });

    const initialState = UIModule.getState();
    const features = DataModule.filter(initialState);
    MapModule.renderFeatures(features);
    UIModule.initialRender();

    if (loadingOverlay) {
      loadingOverlay.classList.add('hidden');
      setTimeout(() => loadingOverlay.remove(), 500);
    }
  } catch (err) {
    console.error('Failed to initialize application:', err);
    if (loadingText) {
      loadingText.textContent =
        'Failed to load data. Make sure you are serving via HTTP (not file://).';
    }
    const spinner = loadingOverlay && loadingOverlay.querySelector('.loading-spinner');
    if (spinner) spinner.style.display = 'none';
  }
})();
