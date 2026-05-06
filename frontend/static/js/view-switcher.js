(function (global) {
  const state = {
    mapInitialized: false,
    sceneInitialized: false,
  };

  function safeCall(fn) {
    try {
      fn();
    } catch (error) {
      if (global.console && typeof global.console.warn === 'function') {
        global.console.warn('View switch operation failed:', error);
      }
    }
  }

  function init3D() {
    if (state.sceneInitialized) {
      return;
    }

    if (typeof global.initScene3D === 'function') {
      safeCall(function () {
        global.initScene3D();
      });
      state.sceneInitialized = true;
    }
  }

  function init2D() {
    if (state.mapInitialized) {
      safeCall(function () {
        global.dispatchEvent(new Event('resize'));
      });
      return;
    }

    if (typeof global.initMap === 'function') {
      safeCall(function () {
        global.initMap();
      });
      state.mapInitialized = true;

      // Give Leaflet time to paint and then force reflow.
      global.setTimeout(function () {
        safeCall(function () {
          global.dispatchEvent(new Event('resize'));
        });
      }, 160);
    }
  }

  function handleViewChange(view) {
    if (view === '2d') {
      init2D();
      return;
    }

    init3D();
  }

  function onTabChanged(event) {
    const detail = (event && event.detail) || {};
    handleViewChange(detail.view || '3d');
  }

  function onViewChanged(event) {
    const detail = (event && event.detail) || {};
    handleViewChange(detail.view || '3d');
  }

  function init() {
    init3D();

    global.addEventListener('xdei:tab-changed', onTabChanged);
    global.addEventListener('xdei:view-changed', onViewChanged);
  }

  if (document.readyState === 'loading') {
    global.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})(window);
