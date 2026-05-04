(function (global) {
  function cloneVehicle(vehicle) {
    return vehicle && typeof vehicle === 'object' ? JSON.parse(JSON.stringify(vehicle)) : vehicle;
  }

  function normalizeVehicleId(vehicle) {
    if (!vehicle || typeof vehicle !== 'object') {
      return '';
    }

    return String(vehicle.vehicleId || vehicle.id || '').trim();
  }

  function cloneVehicles(vehicles) {
    return (Array.isArray(vehicles) ? vehicles : []).map(cloneVehicle);
  }

  function dedupeVehicles(vehicles) {
    const deduped = new Map();

    (Array.isArray(vehicles) ? vehicles : []).forEach((vehicle) => {
      const vehicleId = normalizeVehicleId(vehicle);
      if (!vehicleId) {
        return;
      }

      deduped.set(vehicleId, cloneVehicle(vehicle));
    });

    return Array.from(deduped.values());
  }

  function createFallbackPolling(fetchCurrentVehicles, intervalMs, onData, onError) {
    let timerId = null;
    let inFlight = false;

    async function tick() {
      if (inFlight) {
        return;
      }

      inFlight = true;
      try {
        const vehicles = await fetchCurrentVehicles();
        onData(vehicles);
      } catch (error) {
        onError(error);
      } finally {
        inFlight = false;
      }
    }

    return {
      start() {
        if (timerId) {
          return;
        }

        tick();
        timerId = global.setInterval(tick, intervalMs);
      },
      stop() {
        if (!timerId) {
          return;
        }

        global.clearInterval(timerId);
        timerId = null;
        inFlight = false;
      },
      isRunning() {
        return Boolean(timerId);
      },
    };
  }

  function createVehicleManager(options) {
    const settings = options || {};
    const pollingIntervalMs = Number.isFinite(settings.intervalMs) && settings.intervalMs > 0 ? settings.intervalMs : 2000;
    const subscribers = new Set();
    let vehicles = [];
    let pollingController = null;

    function getApiClient() {
      if (typeof global.MapApiClient !== 'undefined' && global.MapApiClient) {
        return global.MapApiClient;
      }

      return null;
    }

    function fetchCurrentVehicles() {
      const apiClient = getApiClient();
      if (apiClient && typeof apiClient.loadCurrentVehicles === 'function') {
        return apiClient.loadCurrentVehicles();
      }

      return Promise.resolve([]);
    }

    function stopPolling() {
      if (pollingController && typeof pollingController.stop === 'function') {
        pollingController.stop();
      }

      pollingController = null;
    }

    function notifySubscribers(meta) {
      const snapshot = getVehicles();
      subscribers.forEach((subscriber) => {
        try {
          subscriber(snapshot, meta || {});
        } catch (error) {
          if (global.console && typeof global.console.error === 'function') {
            global.console.error('VehicleManager subscriber failed:', error);
          }
        }
      });
    }

    function setVehicles(nextVehicles, meta) {
      vehicles = dedupeVehicles(nextVehicles);
      notifySubscribers(meta || { source: 'setVehicles' });
      return getVehicles();
    }

    function startPolling() {
      if (pollingController && typeof pollingController.isRunning === 'function' && pollingController.isRunning()) {
        return pollingController;
      }

      const apiClient = getApiClient();
      if (apiClient && typeof apiClient.createVehiclePolling === 'function') {
        pollingController = apiClient.createVehiclePolling({
          intervalMs: pollingIntervalMs,
          onData(fetchedVehicles) {
            setVehicles(fetchedVehicles, { source: 'polling' });
          },
          onError(error) {
            if (global.console && typeof global.console.warn === 'function') {
              global.console.warn('VehicleManager polling failed:', error);
            }
          },
        });

        pollingController.start();
        return pollingController;
      }

      pollingController = createFallbackPolling(
        fetchCurrentVehicles,
        pollingIntervalMs,
        (fetchedVehicles) => {
          setVehicles(fetchedVehicles, { source: 'polling' });
        },
        (error) => {
          if (global.console && typeof global.console.warn === 'function') {
            global.console.warn('VehicleManager polling failed:', error);
          }
        }
      );

      pollingController.start();
      return pollingController;
    }

    function getVehicles() {
      return cloneVehicles(vehicles);
    }

    function getVehicle(vehicleId) {
      const targetId = String(vehicleId || '').trim();
      if (!targetId) {
        return null;
      }

      const match = vehicles.find((vehicle) => normalizeVehicleId(vehicle) === targetId);
      return match ? cloneVehicle(match) : null;
    }

    function subscribe(callback, options) {
      if (typeof callback !== 'function') {
        return function () {};
      }

      const settings = options || {};
      subscribers.add(callback);

      if (settings.emitCurrent !== false) {
        callback(getVehicles(), { source: vehicles.length ? 'current' : 'bootstrap' });
      }

      startPolling();

      return function unsubscribe() {
        subscribers.delete(callback);
        if (!subscribers.size) {
          stopPolling();
        }
      };
    }

    function destroy() {
      subscribers.clear();
      stopPolling();
      vehicles = [];
    }

    return {
      start: startPolling,
      stop: stopPolling,
      destroy,
      subscribe,
      setVehicles,
      getVehicles,
      getVehicle,
      isRunning() {
        return Boolean(pollingController && typeof pollingController.isRunning === 'function' && pollingController.isRunning());
      },
      getSubscriberCount() {
        return subscribers.size;
      },
    };
  }

  const defaultManager = createVehicleManager();

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      createVehicleManager,
      vehicleManager: defaultManager,
    };
  }

  global.VehicleManager = defaultManager;
  global.createVehicleManager = createVehicleManager;
})(typeof window !== 'undefined' ? window : globalThis);
