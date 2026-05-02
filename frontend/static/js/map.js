function initMap() {
  const mapEl = document.getElementById('map');
  const statusEl = document.getElementById('map-status');
  const detailPanelEl = document.getElementById('detail-panel');
  const detailPanelBodyEl = document.getElementById('detail-panel-body');
  const detailPanelTitleEl = detailPanelEl ? detailPanelEl.querySelector('.detail-panel__title') : null;
  const detailPanelCloseEl = document.getElementById('detail-panel-close');

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
  const routeIndexByTripId = new Map();
  const routeIndexByStopId = new Map();
  const stopIndexById = new Map();
  const vehicleIndexById = new Map();
  let selectedDetail = null;
  let currentMapData = {
    routes: [],
    stops: [],
    vehicles: [],
  };

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

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setPanelEmpty(message) {
    if (!detailPanelEl || !detailPanelBodyEl) {
      return;
    }

    detailPanelEl.classList.add('detail-panel--empty');
    detailPanelEl.setAttribute('data-detail-type', 'empty');

    if (detailPanelTitleEl) {
      detailPanelTitleEl.textContent = 'Selecciona un vehículo o una parada';
    }

    detailPanelBodyEl.innerHTML = `<p class="detail-panel__empty-state">${escapeHtml(message || 'Haz clic en un vehículo o una parada para ver su información.')}</p>`;
  }

  function setPanelContent(type, title, bodyHtml) {
    if (!detailPanelEl || !detailPanelBodyEl) {
      return;
    }

    detailPanelEl.classList.remove('detail-panel--empty');
    detailPanelEl.setAttribute('data-detail-type', type);

    if (detailPanelTitleEl) {
      detailPanelTitleEl.textContent = title;
    }

    detailPanelBodyEl.innerHTML = bodyHtml;
  }

  function formatNumberMetric(value, suffix) {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return 'N/D';
    }

    return `${value}${suffix}`;
  }

  function formatTimeValue(value) {
    if (!value) {
      return 'N/D';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  }

  function buildRouteIndexes(routes) {
    routeIndexByTripId.clear();
    routeIndexByStopId.clear();

    (routes || []).forEach((route) => {
      if (!route || !route.id) {
        return;
      }

      if (Array.isArray(route.tripIds)) {
        route.tripIds.forEach((tripId) => {
          if (tripId) {
            routeIndexByTripId.set(tripId, route);
          }
        });
      }

      if (Array.isArray(route.stopIds)) {
        route.stopIds.forEach((stopId) => {
          if (stopId) {
            routeIndexByStopId.set(stopId, routeIndexByStopId.get(stopId) || []);
            routeIndexByStopId.get(stopId).push(route);
          }
        });
      }
    });
  }

  function buildStopIndex(stops) {
    stopIndexById.clear();

    (stops || []).forEach((stop) => {
      if (stop && stop.id) {
        stopIndexById.set(stop.id, stop);
      }
    });
  }

  function buildVehicleIndex(vehicles) {
    vehicleIndexById.clear();

    (vehicles || []).forEach((vehicle) => {
      if (vehicle && (vehicle.id || vehicle.vehicleId)) {
        vehicleIndexById.set(vehicle.id || vehicle.vehicleId, vehicle);
      }
    });
  }

  function routeLabel(route) {
    if (!route) {
      return 'Ruta';
    }

    return route.routeLongName || route.routeShortName || route.id || 'Ruta';
  }

  function stopLabel(stop) {
    if (!stop) {
      return 'Parada';
    }

    return stop.stopName || stop.id || 'Parada';
  }

  function findRouteForVehicle(vehicle) {
    if (!vehicle || !vehicle.tripId) {
      return null;
    }

    return routeIndexByTripId.get(vehicle.tripId) || null;
  }

  function findRoutesForStop(stopId) {
    return routeIndexByStopId.get(stopId) || [];
  }

  function renderRouteChips(route) {
    return `<span class="detail-chip">${escapeHtml(routeLabel(route))}</span>`;
  }

  function renderVehiclePanel(vehicle) {
    const route = findRouteForVehicle(vehicle);
    const currentStop = vehicle.currentStopId ? stopIndexById.get(vehicle.currentStopId) : null;
    const routeStops = route && Array.isArray(route.stopIds)
      ? route.stopIds.map((stopId) => stopIndexById.get(stopId)).filter(Boolean)
      : [];

    const nextStops = routeStops.slice(0, 3).map((stop, index) => {
      return `<li>${escapeHtml(stopLabel(stop))}${index === 0 && currentStop ? ' · parada actual' : ''}</li>`;
    }).join('');

    const sections = [];
    sections.push(`
      <section class="detail-panel__section">
        <div class="detail-panel__section-title">Vehículo</div>
        <p class="detail-panel__value">${escapeHtml(vehicle.vehicleId || vehicle.id || 'Sin identificador')}</p>
        <p class="detail-panel__meta">Trip: ${escapeHtml(vehicle.tripId || 'sin asignar')}</p>
        <div class="detail-panel__chips">
          ${route ? renderRouteChips(route) : '<span class="detail-chip">Sin ruta asociada</span>'}
          ${currentStop ? `<span class="detail-chip">${escapeHtml(stopLabel(currentStop))}</span>` : '<span class="detail-chip">Sin parada actual</span>'}
        </div>
      </section>
    `);

    sections.push(`
      <section class="detail-panel__section">
        <div class="detail-panel__section-title">Estado actual</div>
        <p class="detail-panel__meta">Estado: ${escapeHtml(vehicle.status || 'sin estado')}</p>
        <p class="detail-panel__meta">Retraso: ${escapeHtml(formatNumberMetric(vehicle.delaySeconds, ' s'))}</p>
        <p class="detail-panel__meta">Ocupación: ${escapeHtml(formatNumberMetric(vehicle.occupancy, '%'))}</p>
        <p class="detail-panel__meta">Velocidad: ${escapeHtml(formatNumberMetric(vehicle.speedKmh, ' km/h'))}</p>
        ${vehicle.predictedArrivalTime ? `<p class="detail-panel__meta">Próxima llegada: ${escapeHtml(formatTimeValue(vehicle.predictedArrivalTime))}</p>` : ''}
      </section>
    `);

    sections.push(`
      <section class="detail-panel__section">
        <div class="detail-panel__section-title">Próximas paradas</div>
        ${routeStops.length ? `<ol class="detail-panel__list">${nextStops}</ol>` : '<p class="detail-panel__meta">No hay información de paradas asociadas para este vehículo.</p>'}
      </section>
    `);

    setPanelContent('vehicle', `Vehículo ${vehicle.vehicleId || vehicle.id || ''}`.trim(), sections.join(''));
  }

  function renderStopPanel(stop) {
    const routes = findRoutesForStop(stop.id);
    const activeVehicles = Array.from(vehicleIndexById.values()).filter((vehicle) => vehicle.currentStopId === stop.id);

    const sectionRoutes = routes.length
      ? `<div class="detail-panel__chips">${routes.map(renderRouteChips).join('')}</div>`
      : '<p class="detail-panel__meta">No hay rutas asociadas cargadas.</p>';

    const sectionVehicles = activeVehicles.length
      ? `<ul class="detail-panel__list">${activeVehicles.map((vehicle) => `<li>${escapeHtml(vehicle.vehicleId || vehicle.id || 'Vehículo')} · ${escapeHtml(vehicle.status || 'sin estado')}</li>`).join('')}</ul>`
      : '<p class="detail-panel__meta">No hay vehículos en esta parada en este instante.</p>';

    setPanelContent('stop', `Parada ${stop.stopName || stop.id || ''}`.trim(), `
      <section class="detail-panel__section">
        <div class="detail-panel__section-title">Parada</div>
        <p class="detail-panel__value">${escapeHtml(stop.stopName || 'Parada')}</p>
        <p class="detail-panel__meta">Código: ${escapeHtml(stop.stopCode || 'N/D')}</p>
        ${stop.stopDesc ? `<p class="detail-panel__meta">${escapeHtml(stop.stopDesc)}</p>` : ''}
        ${Array.isArray(stop.location) && stop.location.length >= 2 ? `<p class="detail-panel__meta">Coordenadas: ${escapeHtml(stop.location[1])}, ${escapeHtml(stop.location[0])}</p>` : ''}
      </section>
      <section class="detail-panel__section">
        <div class="detail-panel__section-title">Rutas</div>
        ${sectionRoutes}
      </section>
      <section class="detail-panel__section">
        <div class="detail-panel__section-title">Vehículos asociados</div>
        ${sectionVehicles}
      </section>
    `);
  }

  function selectVehicle(vehicle) {
    if (!vehicle) {
      return;
    }

    selectedDetail = { type: 'vehicle', id: vehicle.id || vehicle.vehicleId };
    renderVehiclePanel(vehicle);
  }

  function selectStop(stop) {
    if (!stop) {
      return;
    }

    selectedDetail = { type: 'stop', id: stop.id };
    renderStopPanel(stop);
  }

  function clearDetailPanel() {
    selectedDetail = null;
    setPanelEmpty();
  }

  function refreshSelectedDetail() {
    if (!selectedDetail) {
      return;
    }

    if (selectedDetail.type === 'vehicle') {
      const vehicle = vehicleIndexById.get(selectedDetail.id);
      if (vehicle) {
        renderVehiclePanel(vehicle);
        return;
      }
    }

    if (selectedDetail.type === 'stop') {
      const stop = stopIndexById.get(selectedDetail.id);
      if (stop) {
        renderStopPanel(stop);
        return;
      }
    }

    clearDetailPanel();
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
      marker.on('click', function () {
        selectStop(stop);
      });
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
      marker.on('click', function () {
        selectVehicle(vehicle);
      });
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
    currentMapData = {
      routes: Array.isArray(data.routes) ? data.routes : [],
      stops: Array.isArray(data.stops) ? data.stops : [],
      vehicles: Array.isArray(data.vehicles) ? data.vehicles : [],
    };

    buildRouteIndexes(currentMapData.routes);
    buildStopIndex(currentMapData.stops);
    buildVehicleIndex(currentMapData.vehicles);

    const routeBounds = renderRoutes(data.routes || []);
    const stopBounds = renderStops(data.stops || []);
    const vehicleBounds = renderVehicles(data.vehicles || []);

    if (!mapFitted || settings.fitBounds) {
      fitToData([routeBounds, stopBounds, vehicleBounds]);
      mapFitted = true;
    }

    counters.routes = currentMapData.routes.length;
    counters.stops = currentMapData.stops.length;
    counters.vehicles = currentMapData.vehicles.length;
    refreshStatus('actualizando cada 2s');
    refreshSelectedDetail();
  }

  function updateVehicles(vehicles) {
    currentMapData = {
      routes: currentMapData.routes,
      stops: currentMapData.stops,
      vehicles: Array.isArray(vehicles) ? vehicles : [],
    };

    buildVehicleIndex(currentMapData.vehicles);
    renderVehicles(currentMapData.vehicles);
    counters.vehicles = currentMapData.vehicles.length;
    refreshStatus('actualizando cada 2s');
    refreshSelectedDetail();
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

  if (detailPanelCloseEl) {
    detailPanelCloseEl.addEventListener('click', clearDetailPanel);
  }

  setPanelEmpty();

  loadAndRender();
}

if (typeof window !== 'undefined') window.initMap = initMap;
