(function (global) {
  const SAMPLE_DATA = {
    routes: [
      {
        id: 'urn:ngsi-ld:GtfsRoute:route-1',
        routeShortName: '1',
        routeLongName: 'Praza de Pontevedra - Campus',
        routeColor: '0B74DE',
        routeTextColor: 'FFFFFF',
        path: [
          [-8.4047, 43.3704],
          [-8.4026, 43.3687],
          [-8.4010, 43.3668],
          [-8.3992, 43.3649],
        ],
        tripIds: ['urn:ngsi-ld:GtfsTrip:trip-1'],
        stopIds: ['urn:ngsi-ld:GtfsStop:stop-1', 'urn:ngsi-ld:GtfsStop:stop-2'],
      },
    ],
    stops: [
      {
        id: 'urn:ngsi-ld:GtfsStop:stop-1',
        stopName: 'Praza de Pontevedra',
        stopCode: '0101',
        location: [-8.4047, 43.3704],
      },
      {
        id: 'urn:ngsi-ld:GtfsStop:stop-2',
        stopName: 'Campus Sur',
        stopCode: '0214',
        location: [-8.3997, 43.3649],
      },
    ],
    vehicles: [
      {
        id: 'urn:ngsi-ld:VehicleState:bus-17',
        vehicleId: 'bus-17',
        tripId: 'urn:ngsi-ld:GtfsTrip:trip-1',
        currentStopId: 'urn:ngsi-ld:GtfsStop:stop-1',
        currentPosition: [-8.4029, 43.3680],
        delaySeconds: 45,
        occupancy: 62,
        speedKmh: 26,
        heading: 128,
        status: 'in_transit',
        nextStopName: 'Campus Sur',
        predictedArrivalTime: '2026-05-02T12:08:00Z',
      },
    ],
  };

  function cloneData(data) {
    return JSON.parse(JSON.stringify(data));
  }

  function resolveBackendBaseUrl() {
    const configuredValue = (window.BACKEND_BASE_URL || '').trim().replace(/\/+$/g, '');

    if (configuredValue && configuredValue !== '__BACKEND_BASE_URL__') {
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

  async function fetchJson(path) {
    const base = resolveBackendBaseUrl();
    const url = base ? `${base}${path}` : path;
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
      },
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

      if (!data.routes.length && !data.stops.length && !data.vehicles.length) {
        return cloneData(SAMPLE_DATA);
      }

      return data;
    } catch (error) {
      console.warn('Falling back to sample map data:', error);
      return cloneData(SAMPLE_DATA);
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


          function buildBackendCandidates() {
            const candidates = [];
            const configuredBase = resolveBackendBaseUrl();

            if (configuredBase) {
              candidates.push(configuredBase);
            }

            if (window.location.protocol !== 'file:') {
              const host = window.location.hostname;
              if (host === 'localhost' || host === '127.0.0.1') {
                candidates.push(`${window.location.protocol}//${host}:8000`);
                candidates.push(`${window.location.protocol}//${host}:8002`);
              }
            } else {
              candidates.push('http://127.0.0.1:8000');
              candidates.push('http://127.0.0.1:8002');
            }

            return Array.from(new Set(candidates.filter(Boolean)));
          }

          async function fetchJsonFromBase(base, path) {
            const url = base ? `${base}${path}` : path;
            const response = await fetch(url, {
              headers: {
                Accept: 'application/json',
              },
            });

            if (!response.ok) {
              throw new Error(`Request failed for ${url}: ${response.status}`);
            }

            return response.json();
          }
      page += 1;
    }
            const candidates = buildBackendCandidates();
            let lastError = null;

            for (const base of candidates) {
              try {
                return await fetchJsonFromBase(base, path);
              } catch (error) {
                lastError = error;
              }
    const intervalMs = Number.isFinite(settings.intervalMs) && settings.intervalMs > 0 ? settings.intervalMs : 2000;
    const onData = typeof settings.onData === 'function' ? settings.onData : function () {};
            throw lastError || new Error(`Request failed for ${path}`);

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

  global.MapApiClient = {
    loadMapData,
    loadCurrentVehicles,
    loadStopPredictionSeries,
    loadVehicleHistory,
    loadAllVehicleHistory,
    createVehiclePolling,
    sampleData: () => cloneData(SAMPLE_DATA),
  };
})(window);