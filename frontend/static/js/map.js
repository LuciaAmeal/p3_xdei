function initMap() {
  const mapEl = document.getElementById('map');
  const statusEl = document.getElementById('map-status');

  if (!mapEl || typeof L === 'undefined') {
    return;
  }

  const center = [43.3623, -8.4115];
  const map = L.map('map', { zoomControl: true }).setView(center, 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);

  const routeLayer = L.layerGroup().addTo(map);
  const stopLayer = L.layerGroup().addTo(map);
  const vehicleLayer = L.layerGroup().addTo(map);
  const vehicleMarkers = new Map();
  const vehicleStates = new Map();
  const vehiclePollingIntervalMs = 2000;

  let mapFitted = false;
  let pollingController = null;
  let animationFrameId = null;
  const counters = {
    routes: 0,
    stops: 0,
    vehicles: 0,
  };

  function setStatus(message) {
    if (statusEl) {
      statusEl.textContent = message;
    }
  }

  function refreshStatus(suffix) {
    const base = `Rutas ${counters.routes} · Paradas ${counters.stops} · Vehículos ${counters.vehicles}`;
    setStatus(suffix ? `${base} · ${suffix}` : base);
  }

  function normalizeColor(value, fallback) {
    if (typeof value !== 'string' || !value.trim()) {
      return fallback;
    }

    const raw = value.trim().replace(/^#/, '');
    if (/^[0-9a-fA-F]{6}$/.test(raw)) {
      return `#${raw}`;
    }

    return fallback;
  }

  function hashColor(input) {
    const palette = ['#0B74DE', '#19C98D', '#FF9F1C', '#B04DFF', '#E34C67'];
    let hash = 0;

    for (let index = 0; index < input.length; index += 1) {
      hash = (hash * 31 + input.charCodeAt(index)) % palette.length;
    }

    return palette[Math.abs(hash) % palette.length];
  }

  function pathToLatLngs(path) {
    if (!Array.isArray(path)) {
      return [];
    }

    return path
      .filter((coordinate) => Array.isArray(coordinate) && coordinate.length >= 2)
      .map((coordinate) => [coordinate[1], coordinate[0]]);
  }

  function markerIcon(className, label) {
    return L.divIcon({
      className: '',
      html: `<div class="map-marker ${className}"></div>${label ? `<span class="map-marker-label">${label}</span>` : ''}`,
      iconSize: [18, 18],
      iconAnchor: [9, 9],
      popupAnchor: [0, -10],
    });
  }

  function clamp01(value) {
    return Math.max(0, Math.min(1, value));
  }

  function lerp(start, end, t) {
    return start + (end - start) * t;
  }

  function animateVehicles(timestamp) {
    let keepAnimating = false;

    vehicleStates.forEach((state) => {
      if (!state || !state.marker || !state.startLatLng || !state.targetLatLng) {
        return;
      }

      const duration = Math.max(1, state.endTime - state.startTime);
      const progress = clamp01((timestamp - state.startTime) / duration);
      const lat = lerp(state.startLatLng.lat, state.targetLatLng.lat, progress);
      const lng = lerp(state.startLatLng.lng, state.targetLatLng.lng, progress);
      const interpolated = L.latLng(lat, lng);

      state.currentLatLng = interpolated;
      state.marker.setLatLng(interpolated);

      if (progress < 1) {
        keepAnimating = true;
      } else {
        state.startLatLng = state.targetLatLng;
      }
    });

    if (keepAnimating) {
      animationFrameId = window.requestAnimationFrame(animateVehicles);
      return;
    }

    animationFrameId = null;
  }

  function ensureAnimationLoop() {
    if (animationFrameId !== null) {
      return;
    }

    animationFrameId = window.requestAnimationFrame(animateVehicles);
  }

  function routePopup(route) {
    const stopCount = Array.isArray(route.stopIds) ? route.stopIds.length : 0;
    const tripCount = Array.isArray(route.tripIds) ? route.tripIds.length : 0;
    const title = route.routeLongName || route.routeShortName || 'Ruta sin nombre';
    const shortName = route.routeShortName ? `Línea ${route.routeShortName}` : 'Ruta';
    const stops = Array.isArray(route.stops) ? route.stops : [];

    return `
      <div class="popup-title">${title}</div>
      <div class="popup-meta">${shortName}</div>
      <div class="popup-meta">${tripCount} viajes · ${stopCount} paradas</div>
      ${stops.length ? `<ul class="popup-list">${stops.map((stop) => `<li>${stop.stopName || stop.id}</li>`).join('')}</ul>` : ''}
    `;
  }

  function stopPopup(stop) {
    return `
      <div class="popup-title">${stop.stopName || 'Parada'}</div>
      <div class="popup-meta">${stop.stopCode || stop.id}</div>
      ${stop.stopDesc ? `<div class="popup-meta">${stop.stopDesc}</div>` : ''}
    `;
  }

  function vehiclePopup(vehicle) {
    const occupancy = typeof vehicle.occupancy === 'number' ? `${vehicle.occupancy}%` : 'N/D';
    const delay = typeof vehicle.delaySeconds === 'number' ? `${vehicle.delaySeconds}s` : 'N/D';
    const speed = typeof vehicle.speedKmh === 'number' ? `${vehicle.speedKmh} km/h` : 'N/D';

    return `
      <div class="popup-title">Vehículo ${vehicle.vehicleId || vehicle.id}</div>
      <div class="popup-meta">Estado: ${vehicle.status || 'sin estado'}</div>
      <div class="popup-meta">Trip: ${vehicle.tripId || 'sin asignar'}</div>
      <div class="popup-meta">Retraso: ${delay} · Ocupación: ${occupancy} · Velocidad: ${speed}</div>
      ${vehicle.nextStopName ? `<div class="popup-meta">Próxima parada: ${vehicle.nextStopName}</div>` : ''}
    `;
  }

  function renderRoutes(routes) {
    routeLayer.clearLayers();
    const bounds = L.latLngBounds([]);

    routes.forEach((route) => {
      const latLngs = pathToLatLngs(route.path);
      if (!latLngs.length) {
        return;
      }

      const color = normalizeColor(route.routeColor, hashColor(route.id || route.routeShortName || 'route'));
      const polyline = L.polyline(latLngs, {
        color,
        weight: 5,
        opacity: 0.88,
        lineCap: 'round',
        lineJoin: 'round',
      });

      polyline.bindPopup(routePopup(route));
      polyline.addTo(routeLayer);
      bounds.extend(polyline.getBounds());
    });

    return bounds;
  }

  function renderStops(stops) {
    stopLayer.clearLayers();
    const bounds = L.latLngBounds([]);

    stops.forEach((stop) => {
      if (!Array.isArray(stop.location) || stop.location.length < 2) {
        return;
      }

      const marker = L.marker([stop.location[1], stop.location[0]], {
        icon: markerIcon('map-marker--stop', stop.stopName ? stop.stopName.slice(0, 2).toUpperCase() : 'S'),
        title: stop.stopName || stop.id,
      });

      marker.bindPopup(stopPopup(stop));
      marker.addTo(stopLayer);
      bounds.extend(marker.getLatLng());
    });

    return bounds;
  }

  function renderVehicles(vehicles) {
    const bounds = L.latLngBounds([]);
    const activeVehicleIds = new Set();
    const now = window.performance && typeof window.performance.now === 'function'
      ? window.performance.now()
      : Date.now();

    vehicles.forEach((vehicle) => {
      if (!Array.isArray(vehicle.currentPosition) || vehicle.currentPosition.length < 2) {
        return;
      }

      const vehicleId = vehicle.id || vehicle.vehicleId;
      if (!vehicleId) {
        return;
      }

      activeVehicleIds.add(vehicleId);
      const latLng = L.latLng(vehicle.currentPosition[1], vehicle.currentPosition[0]);

      const existingMarker = vehicleMarkers.get(vehicleId);
      if (existingMarker) {
        const state = vehicleStates.get(vehicleId);
        const currentLatLng = state && state.currentLatLng ? state.currentLatLng : existingMarker.getLatLng();

        if (state) {
          state.startLatLng = currentLatLng;
          state.targetLatLng = latLng;
          state.startTime = now;
          state.endTime = now + vehiclePollingIntervalMs;
        }

        existingMarker.setPopupContent(vehiclePopup(vehicle));
        bounds.extend(latLng);
        return;
      }

      const marker = L.marker(latLng, {
        icon: markerIcon('map-marker--vehicle', vehicle.vehicleId ? vehicle.vehicleId.replace(/^bus-/, '') : 'V'),
        title: vehicle.vehicleId || vehicle.id,
      });

      marker.bindPopup(vehiclePopup(vehicle));
      marker.addTo(vehicleLayer);
      vehicleMarkers.set(vehicleId, marker);
      vehicleStates.set(vehicleId, {
        marker,
        currentLatLng: latLng,
        startLatLng: latLng,
        targetLatLng: latLng,
        startTime: now,
        endTime: now + vehiclePollingIntervalMs,
      });
      bounds.extend(latLng);
    });

    vehicleMarkers.forEach((marker, vehicleId) => {
      if (activeVehicleIds.has(vehicleId)) {
        return;
      }

      vehicleLayer.removeLayer(marker);
      vehicleMarkers.delete(vehicleId);
      vehicleStates.delete(vehicleId);
    });

    ensureAnimationLoop();

    return bounds;
  }

  function fitToData(boundsList) {
    const validBounds = boundsList.filter((bounds) => bounds && typeof bounds.isValid === 'function' && bounds.isValid());
    if (!validBounds.length) {
      return;
    }

    const [firstBounds, ...restBounds] = validBounds;
    const merged = restBounds.reduce(
      (accumulator, bounds) => accumulator.extend(bounds),
      L.latLngBounds(firstBounds.getSouthWest(), firstBounds.getNorthEast())
    );
    if (merged.isValid()) {
      map.fitBounds(merged.pad(0.18));
    }
  }

  function updateMap(data, options) {
    const settings = options || {};
    const routeBounds = renderRoutes(data.routes || []);
    const stopBounds = renderStops(data.stops || []);
    const vehicleBounds = renderVehicles(data.vehicles || []);

    if (!mapFitted || settings.fitBounds) {
      fitToData([routeBounds, stopBounds, vehicleBounds]);
      mapFitted = true;
    }

    counters.routes = (data.routes || []).length;
    counters.stops = (data.stops || []).length;
    counters.vehicles = (data.vehicles || []).length;
    refreshStatus('actualizando cada 2s');
  }

  function updateVehicles(vehicles) {
    renderVehicles(vehicles || []);
    counters.vehicles = (vehicles || []).length;
    refreshStatus('actualizando cada 2s');
  }

  function startVehiclePolling() {
    if (!window.MapApiClient || typeof window.MapApiClient.createVehiclePolling !== 'function') {
      return;
    }

    if (pollingController && pollingController.isRunning()) {
      return;
    }

    pollingController = window.MapApiClient.createVehiclePolling({
      intervalMs: vehiclePollingIntervalMs,
      onData: function (vehicles) {
        updateVehicles(vehicles);
      },
      onError: function (error) {
        console.warn('Vehicle polling failed:', error);
        refreshStatus('reintentando conexion');
      },
    });

    pollingController.start();
  }

  function loadAndRender() {
    setStatus('Cargando datos de movilidad…');

    const loader = window.MapApiClient && typeof window.MapApiClient.loadMapData === 'function'
      ? window.MapApiClient.loadMapData()
      : Promise.resolve(window.MapApiClient ? window.MapApiClient.sampleData() : { routes: [], stops: [], vehicles: [] });

    loader
      .then((data) => {
        updateMap(data, { fitBounds: true });
        startVehiclePolling();
      })
      .catch((error) => {
        console.warn('Unable to render map data:', error);
        if (window.MapApiClient && typeof window.MapApiClient.sampleData === 'function') {
          updateMap(window.MapApiClient.sampleData(), { fitBounds: true });
          startVehiclePolling();
        }
        setStatus('Mostrando datos de muestra');
      });
  }

  window.addEventListener('resize', function () {
    map.invalidateSize();
  });

  window.addEventListener('beforeunload', function () {
    if (pollingController) {
      pollingController.stop();
    }

    if (animationFrameId !== null) {
      window.cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
  });

  loadAndRender();
}

if (typeof window !== 'undefined') window.initMap = initMap;
