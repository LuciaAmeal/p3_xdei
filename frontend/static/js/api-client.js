(function (global) {
  function createEmptyMapData() {
    return {
      routes: [],
      stops: [],
      vehicles: [],
    };
  }

  function resolveBackendBaseUrl() {
    const configuredValue = (window.BACKEND_BASE_URL || '').trim().replace(/\/+$/g, '');

    if (configuredValue && configuredValue !== '__BACKEND_BASE_URL__') {
      try {
        const configuredUrl = new URL(configuredValue);
        if (configuredUrl.hostname === 'backend') {
          if (window.location.protocol === 'file:') {
            return 'http://127.0.0.1:8000';
          }

          if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return `${window.location.protocol}//${window.location.hostname}:8000`;
          }

          return configuredValue;
        }

        return configuredValue;
      } catch (error) {
        // Keep the configured value if it is not a valid URL.
      }

      if (window.location.protocol === 'file:') {
        return 'http://127.0.0.1:8000';
      }

      if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return `${window.location.protocol}//${window.location.hostname}:8000`;
      }

      return configuredValue;
    }

    if (window.location.protocol === 'file:') {
      return 'http://127.0.0.1:8000';
    }

    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }

    return '';
  }

  function buildQueryString(params) {
    const searchParams = new URLSearchParams();

    Object.entries(params || {}).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') {
        return;
      }

      searchParams.set(key, String(value));
    });

    return searchParams.toString();
  }

  async function fetchJson(path, extraHeaders) {
    const base = resolveBackendBaseUrl();
    const url = base ? `${base}${path}` : path;
    const headers = {
      Accept: 'application/json',
    };
    if (extraHeaders && typeof extraHeaders === 'object') {
      Object.assign(headers, extraHeaders);
    }
    const response = await fetch(url, {
      headers,
    });

    if (!response.ok) {
      throw new Error(`Request failed for ${url}: ${response.status}`);
    }

    return response.json();
  }

  async function loadMapData() {
    try {
      const [routesResponse, stopsResponse, vehiclesResponse] = await Promise.all([
        fetchJson('/api/routes'),
        fetchJson('/api/stops'),
        fetchJson('/api/vehicles/current'),
      ]);

      const data = {
        routes: Array.isArray(routesResponse.routes) ? routesResponse.routes : [],
        stops: Array.isArray(stopsResponse.stops) ? stopsResponse.stops : [],
        vehicles: Array.isArray(vehiclesResponse.vehicles) ? vehiclesResponse.vehicles : [],
      };

      return data;
    } catch (error) {
      console.error('Unable to load map data from backend:', error);
      throw error instanceof Error ? error : new Error('Unable to load map data from backend');
    }
  }

  async function loadCurrentVehicles() {
    const vehiclesResponse = await fetchJson('/api/vehicles/current');
    return Array.isArray(vehiclesResponse.vehicles) ? vehiclesResponse.vehicles : [];
  }

  async function loadStopPredictionSeries(stopId, options) {
    const settings = options || {};
    const query = buildQueryString({
      dateTime: settings.dateTime,
      horizonMinutes: settings.horizonMinutes,
      seriesHorizonMinutes: settings.seriesHorizonMinutes,
      stepMinutes: settings.stepMinutes,
    });

    return fetchJson(`/api/stops/${encodeURIComponent(stopId)}/prediction${query ? `?${query}` : ''}`);
  }

  async function loadVehicleHistory(options) {
    const settings = options || {};
    const query = buildQueryString({
      fromDate: settings.fromDate,
      toDate: settings.toDate,
      page: settings.page,
      pageSize: settings.pageSize,
      vehicleId: settings.vehicleId,
    });
    const response = await fetchJson(`/api/vehicles/history${query ? `?${query}` : ''}`);

    return {
      vehicles: Array.isArray(response.vehicles) ? response.vehicles : [],
      pagination: response.pagination || {
        page: 1,
        pageSize: 0,
        totalVehicles: 0,
        totalPages: 0,
      },
      filters: response.filters || {},
    };
  }

  async function loadAllVehicleHistory(options) {
    const settings = options || {};
    const pageSize = Number.isFinite(settings.pageSize) && settings.pageSize > 0 ? settings.pageSize : 100;
    const collectedVehicles = [];
    let page = Number.isFinite(settings.page) && settings.page > 0 ? settings.page : 1;
    let pagination = {
      page,
      pageSize,
      totalVehicles: 0,
      totalPages: 0,
    };
    let filters = {};

    while (true) {
      const response = await loadVehicleHistory({
        fromDate: settings.fromDate,
        toDate: settings.toDate,
        vehicleId: settings.vehicleId,
        page,
        pageSize,
      });

      collectedVehicles.push(...response.vehicles);
      pagination = response.pagination || pagination;
      filters = response.filters || filters;

      if (!pagination.totalPages || page >= pagination.totalPages) {
        break;
      }
      page += 1;
    }

    return {
      vehicles: collectedVehicles,
      pagination,
      filters,
    };
  }

  function createVehiclePolling(options) {
    const settings = options || {};
    const intervalMs = Number.isFinite(settings.intervalMs) && settings.intervalMs > 0 ? settings.intervalMs : 2000;
    const onData = typeof settings.onData === 'function' ? settings.onData : function () {};
    const onError = typeof settings.onError === 'function' ? settings.onError : function () {};

    let timerId = null;
    let inFlight = false;

    async function tick() {
      if (inFlight) {
        return;
      }

      inFlight = true;
      try {
        const vehicles = await loadCurrentVehicles();
        onData(vehicles);
      } catch (error) {
        onError(error);
      } finally {
        inFlight = false;
      }
    }

    function start() {
      if (timerId) {
        return;
      }

      tick();
      timerId = window.setInterval(tick, intervalMs);
    }

    function stop() {
      if (!timerId) {
        return;
      }

      window.clearInterval(timerId);
      timerId = null;
      inFlight = false;
    }

    return {
      start,
      stop,
      isRunning: function () {
        return Boolean(timerId);
      },
      intervalMs,
    };
  }

  async function postJson(path, body) {
    const base = resolveBackendBaseUrl();
    const url = base ? `${base}${path}` : path;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      let detail = '';
      try {
        const errorBody = await response.json();
        detail = errorBody.error || errorBody.detail || '';
      } catch (_ignored) {
        // ignore parse errors
      }
      throw new Error(detail || `Request failed for ${url}: ${response.status}`);
    }

    return response.json();
  }

  async function loadGamificationProfile(userId, options) {
    const settings = options || {};
    const displayName = settings.displayName || userId;
    const authHeaders = { 'X-User-Id': userId };
    // Try to load existing profile; if 404, record a dummy trip to bootstrap it
    try {
      return await fetchJson(`/api/user/${encodeURIComponent(userId)}/profile`, authHeaders);
    } catch (_loadError) {
      // Profile may not exist yet — create it by recording a trip
      try {
        return await postJson('/api/user/record-trip', {
          userId: userId,
          displayName: displayName,
          tripId: 'bootstrap',
          stopId: '',
        });
      } catch (createError) {
        // If creation also fails, try loading one more time
        return await fetchJson(`/api/user/${encodeURIComponent(userId)}/profile`, authHeaders);
      }
    }
  }

  function _resolveHeaders(userId) {
    const headers = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };
    if (userId) {
      headers['X-User-Id'] = userId;
    }
    return headers;
  }

  async function redeemDiscount(options) {
    const settings = options || {};
    const base = resolveBackendBaseUrl();
    const url = base ? `${base}/api/user/redeem` : '/api/user/redeem';
    const response = await fetch(url, {
      method: 'POST',
      headers: _resolveHeaders(settings.userId),
      body: JSON.stringify({
        userId: settings.userId,
        displayName: settings.displayName,
        discountCode: settings.discountCode,
        discountValue: settings.discountValue,
        pointsCost: settings.pointsCost,
        validUntil: settings.validUntil,
      }),
    });

    if (!response.ok) {
      let detail = '';
      try {
        const errorBody = await response.json();
        detail = errorBody.error || errorBody.detail || '';
      } catch (_ignored) {
        // ignore
      }
      throw new Error(detail || `Redeem failed: ${response.status}`);
    }

    return response.json();
  }

  async function recordTrip(options) {
    const settings = options || {};
    return postJson('/api/user/record-trip', {
      userId: settings.userId,
      displayName: settings.displayName,
      tripId: settings.tripId,
      stopId: settings.stopId,
    });
  }

  global.MapApiClient = {
    loadMapData,
    loadCurrentVehicles,
    loadStopPredictionSeries,
    loadVehicleHistory,
    loadAllVehicleHistory,
    createVehiclePolling,
    createEmptyMapData,
    loadGamificationProfile,
    redeemDiscount,
    recordTrip,
  };
})(window);