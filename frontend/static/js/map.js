function initMap() {
  const mapEl = document.getElementById('map');
  const statusEl = document.getElementById('map-status');
  const timelinePanelEl = document.getElementById('timeline-panel');
  const timelineStatusEl = document.getElementById('timeline-status');
  const timelineRangeEl = document.getElementById('timeline-slider');
  const timelineLabelEl = document.getElementById('timeline-label');
  const timelineCountEl = document.getElementById('timeline-count');
  const timelinePlayEl = document.getElementById('timeline-play');
  const timelineLiveEl = document.getElementById('timeline-live');
  const dateFromEl = document.getElementById('date-from');
  const dateToEl = document.getElementById('date-to');
  const dateFilterApplyEl = document.getElementById('date-filter-apply');
  const replaySpeedEl = document.getElementById('replay-speed');
  const vehicleFiltersToggleEl = document.getElementById('vehicle-filters-toggle');
  const vehicleFiltersListEl = document.getElementById('vehicle-filters-list');
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
  const stopPredictionCharts = new Map();
  const stopPredictionRequests = new Map();
  const stopPredictionSummaryHorizonMinutes = 30;
  const stopPredictionSeriesHorizonMinutes = 120;
  const stopPredictionSeriesStepMinutes = 15;
  const routeIndexByTripId = new Map();
  const routeIndexByStopId = new Map();
  const stopIndexById = new Map();
  const vehicleIndexById = new Map();
  let selectedDetail = null;
  let replayHistory = [];
  let replayTimestamps = [];
  let replayCursor = 0;
  let replayTimerId = null;
  let replayActive = false;
  let replayController = null;
  let vehicleTrails = new Map();
  let vehicleManagerUnsubscribe = null;
  let currentMapData = {
    routes: [],
    stops: [],
    vehicles: [],
  };

  let mapFitted = false;
  let animationFrameId = null;
  const counters = {
    routes: 0,
    stops: 0,
    vehicles: 0,
  };
  const baseReplayIntervalMs = 1100;

  function setStatus(message) {
    if (statusEl) {
      statusEl.textContent = message;
    }
  }

  function refreshStatus(suffix) {
    const base = `Rutas ${counters.routes} · Paradas ${counters.stops} · Vehículos ${counters.vehicles}`;
    setStatus(suffix ? `${base} · ${suffix}` : base);
  }

  function setTimelineStatus(message) {
    if (timelineStatusEl) {
      timelineStatusEl.textContent = message;
    }
  }

  function setTimelineControlsDisabled(disabled) {
    if (timelineRangeEl) {
      timelineRangeEl.disabled = disabled;
    }

    if (timelinePlayEl) {
      timelinePlayEl.disabled = disabled;
    }

    if (timelineLiveEl) {
      timelineLiveEl.disabled = disabled;
    }
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

  function formatPercentageValue(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return 'N/D';
    }

    return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
  }

  function formatReplayLabel(value) {
    if (!value) {
      return 'Sin histórico';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleString('es-ES', {
      dateStyle: 'medium',
      timeStyle: 'medium',
    });
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

  function getVehicleManager() {
    if (typeof window.VehicleManager === 'undefined' || !window.VehicleManager) {
      return null;
    }

    return window.VehicleManager;
  }

  function buildReplayIndex(historyVehicles) {
    // Initialize ReplayController with history data
    if (typeof ReplayController !== 'undefined') {
      replayController = new ReplayController(historyVehicles || []);
    } else {
      console.warn('ReplayController not available');
      replayController = null;
    }

    if (!replayController || !Array.isArray(historyVehicles) || !historyVehicles.length) {
      replayHistory = [];
      replayTimestamps = [];
      replayCursor = 0;
      setTimelineControlsDisabled(true);
      setTimelineStatus('Sin datos históricos');
      if (timelineCountEl) {
        timelineCountEl.textContent = '0 vehículos';
      }
      if (timelineLabelEl) {
        timelineLabelEl.textContent = 'No hay histórico disponible';
      }
      clearVehicleTrails();
      return;
    }

    // Use ReplayController to get initial data
    replayHistory = replayController.getFilteredHistory();
    replayTimestamps = replayController.getFilteredTimestamps();
    replayCursor = replayTimestamps.length ? replayTimestamps.length - 1 : 0;
    setTimelineControlsDisabled(!replayTimestamps.length);
    setTimelineStatus(replayTimestamps.length ? 'Histórico listo' : 'Sin datos históricos');

    if (timelineCountEl) {
      timelineCountEl.textContent = `${replayHistory.length} vehículos · ${replayTimestamps.length} instantes`;
    }

    if (timelineRangeEl) {
      timelineRangeEl.min = '0';
      timelineRangeEl.max = String(Math.max(0, replayTimestamps.length - 1));
      timelineRangeEl.step = '1';
      timelineRangeEl.value = String(replayCursor);
    }

    if (timelineLabelEl) {
      timelineLabelEl.textContent = replayTimestamps.length
        ? formatReplayLabel(replayTimestamps[replayCursor])
        : 'No hay histórico disponible';
    }

    // Build vehicle filter checkboxes
    buildVehicleFilterCheckboxes();
  }

  function pickHistoryRecord(history, timestamp) {
    if (!Array.isArray(history) || !history.length || !timestamp) {
      return null;
    }

    const targetTime = new Date(timestamp).getTime();
    if (Number.isNaN(targetTime)) {
      return null;
    }

    let selected = history[0];

    history.forEach((entry) => {
      const entryTime = new Date(entry.timestamp).getTime();
      if (!Number.isNaN(entryTime) && entryTime <= targetTime) {
        selected = entry;
      }
    });

    return selected;
  }

  function buildReplaySnapshot(timestamp) {
    return replayHistory
      .filter(vehicle => replayController && replayController.isVehicleSelected(vehicle.vehicleId))
      .map((vehicle) => {
        const historyRecord = pickHistoryRecord(vehicle.history, timestamp);
        if (!historyRecord || !Array.isArray(historyRecord.currentPosition)) {
          return null;
        }

        return {
          id: vehicle.id,
          vehicleId: vehicle.vehicleId,
          tripId: historyRecord.trip || historyRecord.tripId,
          currentStopId: historyRecord.currentStopId,
          currentPosition: historyRecord.currentPosition,
          delaySeconds: historyRecord.delaySeconds,
          occupancy: historyRecord.occupancy,
          speedKmh: historyRecord.speedKmh,
          heading: historyRecord.heading,
          status: historyRecord.status,
          nextStopName: historyRecord.nextStopName,
          predictedArrivalTime: historyRecord.predictedArrivalTime,
        };
      })
      .filter(Boolean);
  }

  function renderReplayFrame(options) {
    const settings = options || {};
    if (!replayTimestamps.length) {
      return;
    }

    const timestamp = replayTimestamps[replayCursor];
    const snapshotVehicles = buildReplaySnapshot(timestamp);

    if (timelineLabelEl) {
      timelineLabelEl.textContent = formatReplayLabel(timestamp);
    }

    updateVehicles(snapshotVehicles, { animate: settings.animate !== false });
  }

  function stopReplayPlayback() {
    if (replayTimerId !== null) {
      window.clearInterval(replayTimerId);
      replayTimerId = null;
    }

    if (timelinePlayEl) {
      timelinePlayEl.textContent = 'Reproducir';
      timelinePlayEl.setAttribute('aria-pressed', 'false');
    }
  }

  function enterReplayMode() {
    if (!replayTimestamps.length) {
      return;
    }

    replayActive = true;
    setTimelineStatus('Reproducción histórica activa');
    if (timelineLiveEl) {
      timelineLiveEl.textContent = 'Volver a vivo';
    }
  }

  function returnToLiveMode() {
    replayActive = false;
    stopReplayPlayback();
    setTimelineStatus('Vista en vivo');
    if (timelineLiveEl) {
      timelineLiveEl.textContent = 'Vista en vivo';
    }

    if (timelineLabelEl && replayTimestamps.length) {
      timelineLabelEl.textContent = formatReplayLabel(replayTimestamps[replayTimestamps.length - 1]);
    }

    const manager = getVehicleManager();
    if (manager && typeof manager.getVehicles === 'function') {
      updateVehicles(manager.getVehicles(), { animate: false });
    } else if (currentMapData && Array.isArray(currentMapData.vehicles)) {
      updateVehicles(currentMapData.vehicles, { animate: false });
    }
  }

  function seekReplay(cursor, options) {
    if (!replayTimestamps.length) {
      return;
    }

    const clampedCursor = Math.max(0, Math.min(replayTimestamps.length - 1, cursor));
    replayCursor = clampedCursor;

    if (timelineRangeEl) {
      timelineRangeEl.value = String(clampedCursor);
    }

    renderReplayFrame(options);
  }

  function startReplayPlayback() {
    if (!replayTimestamps.length) {
      return;
    }

    enterReplayMode();

    if (replayCursor >= replayTimestamps.length - 1) {
      replayCursor = 0;
    }

    stopReplayPlayback();
    if (timelinePlayEl) {
      timelinePlayEl.textContent = 'Pausar';
      timelinePlayEl.setAttribute('aria-pressed', 'true');
    }

    renderReplayFrame({ animate: false });

    // Calculate interval based on replay speed
    const replayInterval = replayController
      ? replayController.getAdjustedInterval(baseReplayIntervalMs)
      : baseReplayIntervalMs;

    replayTimerId = window.setInterval(function () {
      if (replayCursor >= replayTimestamps.length - 1) {
        stopReplayPlayback();
        return;
      }

      seekReplay(replayCursor + 1, { animate: false });
    }, replayInterval);
  }

  function toggleReplayPlayback() {
    if (!replayTimestamps.length) {
      return;
    }

    if (replayTimerId !== null) {
      stopReplayPlayback();
      return;
    }

    startReplayPlayback();
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

  function destroyStopPredictionChart(stopId) {
    const existingChart = stopPredictionCharts.get(stopId);
    if (existingChart && typeof existingChart.destroy === 'function') {
      existingChart.destroy();
    }

    stopPredictionCharts.delete(stopId);
  }

  function renderStopPredictionChart(stopId, popupElement, prediction) {
    if (!popupElement || !prediction) {
      return;
    }

    const root = popupElement.querySelector('[data-stop-prediction-root]');
    if (!root) {
      return;
    }

    const valueEl = root.querySelector('[data-stop-prediction-value]');
    const statusEl = root.querySelector('[data-stop-prediction-status]');
    const canvasEl = root.querySelector('.stop-prediction__chart');

    if (valueEl) {
      valueEl.textContent = formatPercentageValue(prediction.predictedOccupancy);
    }

    if (statusEl) {
      const confidence = typeof prediction.confidence === 'number' ? `${Math.round(prediction.confidence * 100)}%` : 'N/D';
      const stepMinutes = prediction.seriesStepMinutes || prediction.horizonMinutes || stopPredictionSeriesStepMinutes;
      statusEl.textContent = `Confianza ${confidence} · paso ${stepMinutes} min`;
    }

    if (!canvasEl || typeof window.Chart === 'undefined') {
      if (statusEl) {
        statusEl.textContent = 'El gráfico no está disponible en este navegador.';
      }
      return;
    }

    destroyStopPredictionChart(stopId);

    const series = Array.isArray(prediction.series) ? prediction.series : [];
    const labels = series.map((point) => formatTimeValue(point.timestamp));
    const values = series.map((point) => (typeof point.predictedOccupancy === 'number' ? point.predictedOccupancy : null));

    const chart = new window.Chart(canvasEl.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Ocupación prevista',
            data: values,
            borderColor: '#ffcf5a',
            backgroundColor: 'rgba(255, 207, 90, 0.14)',
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return ` ${context.parsed.y}%`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: 'rgba(245, 247, 251, 0.7)',
              maxRotation: 0,
              autoSkip: true,
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.08)',
            },
          },
          y: {
            beginAtZero: true,
            suggestedMax: 100,
            ticks: {
              color: 'rgba(245, 247, 251, 0.7)',
              callback: function (value) {
                return `${value}%`;
              },
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.08)',
            },
          },
        },
      },
    });

    stopPredictionCharts.set(stopId, chart);
  }

  function loadStopPrediction(stop, popup) {
    if (!stop || !stop.id || !popup || typeof popup.getElement !== 'function' || !window.MapApiClient || typeof window.MapApiClient.loadStopPredictionSeries !== 'function') {
      return;
    }

    const popupElement = popup.getElement();
    if (!popupElement) {
      return;
    }

    const root = popupElement.querySelector('[data-stop-prediction-root]');
    if (!root) {
      return;
    }

    const valueEl = root.querySelector('[data-stop-prediction-value]');
    const statusEl = root.querySelector('[data-stop-prediction-status]');

    if (valueEl) {
      valueEl.textContent = 'Cargando…';
    }

    if (statusEl) {
      statusEl.textContent = 'Consultando predicción de parada…';
    }

    let request = stopPredictionRequests.get(stop.id);
    if (!request) {
      request = window.MapApiClient.loadStopPredictionSeries(stop.id, {
        horizonMinutes: stopPredictionSummaryHorizonMinutes,
        seriesHorizonMinutes: stopPredictionSeriesHorizonMinutes,
        stepMinutes: stopPredictionSeriesStepMinutes,
      });
      stopPredictionRequests.set(stop.id, request);
    }

    request
      .then((prediction) => {
        if (!popupElement.isConnected) {
          return;
        }

        renderStopPredictionChart(stop.id, popupElement, prediction);
      })
      .catch((error) => {
        console.warn('Unable to load stop prediction:', error);
        if (statusEl) {
          statusEl.textContent = 'No se pudo cargar la predicción.';
        }
      })
      .finally(() => {
        if (stopPredictionRequests.get(stop.id) === request) {
          stopPredictionRequests.delete(stop.id);
        }
      });
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
    const stopId = stop && stop.id ? stop.id : '';
    return `
      <div class="popup-title">${escapeHtml(stop.stopName || 'Parada')}</div>
      <div class="popup-meta">${escapeHtml(stop.stopCode || stop.id || 'N/D')}</div>
      ${stop.stopDesc ? `<div class="popup-meta">${escapeHtml(stop.stopDesc)}</div>` : ''}
      <div class="stop-prediction" data-stop-prediction-root data-stop-id="${escapeHtml(stopId)}">
        <div class="stop-prediction__summary">
          <span class="stop-prediction__eyebrow">Próximas 2 horas</span>
          <span class="stop-prediction__value" data-stop-prediction-value>Predicción en carga…</span>
        </div>
        <div class="stop-prediction__meta" data-stop-prediction-status>Abre la parada para ver la curva prevista.</div>
        <div class="stop-prediction__chart-wrap">
          <canvas class="stop-prediction__chart" height="170"></canvas>
        </div>
      </div>
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
      const latLngs = Array.isArray(route.path) ? pathToLatLngs(route.path) : [];

      const drawPolyline = (coords) => {
        const ll = pathToLatLngs(coords);
        if (!ll.length) {
          return;
        }
        const color = normalizeColor(route.routeColor, hashColor(route.id || route.routeShortName || 'route'));
        const polyline = L.polyline(ll, {
          color,
          weight: 5,
          opacity: 0.88,
          lineCap: 'round',
          lineJoin: 'round',
        });

        polyline.bindPopup(routePopup(route));
        polyline.addTo(routeLayer);
        bounds.extend(polyline.getBounds());
      };

      if (latLngs.length) {
        drawPolyline(route.path);
        return;
      }

      // If no path provided, attempt lazy-load via shapeId
      if (route.shapeId && window.MapApiClient && typeof window.MapApiClient.loadShape === 'function') {
        window.MapApiClient.loadShape(route.shapeId)
          .then((resp) => {
            if (resp && Array.isArray(resp.path) && resp.path.length) {
              drawPolyline(resp.path);
            }
          })
          .catch((err) => {
            console.warn('Unable to lazy-load shape for route', route.id, err);
          });
      }
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
      marker.on('popupopen', function (event) {
        loadStopPrediction(stop, event.popup);
      });
      marker.on('popupclose', function () {
        destroyStopPredictionChart(stop.id);
      });
      marker.on('click', function () {
        selectStop(stop);
      });
      marker.addTo(stopLayer);
      bounds.extend(marker.getLatLng());
    });

    return bounds;
  }

  function renderVehicles(vehicles, options) {
    const settings = options || {};
    const animate = settings.animate !== false;
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
        const targetLatLng = latLng;

        if (state) {
          state.startLatLng = animate ? currentLatLng : targetLatLng;
          state.targetLatLng = targetLatLng;
          state.startTime = now;
          state.endTime = now + vehiclePollingIntervalMs;
          if (!animate) {
            state.currentLatLng = targetLatLng;
            existingMarker.setLatLng(targetLatLng);
          }
        }

        existingMarker.setPopupContent(vehiclePopup(vehicle));
        bounds.extend(targetLatLng);
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

      if (!animate) {
        marker.setLatLng(latLng);
      }
    });

    vehicleMarkers.forEach((marker, vehicleId) => {
      if (activeVehicleIds.has(vehicleId)) {
        return;
      }

      vehicleLayer.removeLayer(marker);
      vehicleMarkers.delete(vehicleId);
      vehicleStates.delete(vehicleId);
    });

    if (animate) {
      ensureAnimationLoop();
    }

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
    const vehicleBounds = renderVehicles(data.vehicles || [], { animate: settings.animate !== false });

    if (!mapFitted || settings.fitBounds) {
      fitToData([routeBounds, stopBounds, vehicleBounds]);
      mapFitted = true;
    }

    counters.routes = currentMapData.routes.length;
    counters.stops = currentMapData.stops.length;
    counters.vehicles = currentMapData.vehicles.length;
    refreshStatus(replayActive ? 'reproducción histórica' : 'actualizando cada 2s');
    refreshSelectedDetail();
  }

  function updateVehicles(vehicles, options) {
    const settings = options || {};
    currentMapData = {
      routes: currentMapData.routes,
      stops: currentMapData.stops,
      vehicles: Array.isArray(vehicles) ? vehicles : [],
    };

    buildVehicleIndex(currentMapData.vehicles);
    renderVehicles(currentMapData.vehicles, { animate: settings.animate !== false });
    counters.vehicles = currentMapData.vehicles.length;
    refreshStatus(replayActive ? 'reproducción histórica' : 'actualizando cada 2s');
    refreshSelectedDetail();
  }

  function connectVehicleManager() {
    const manager = getVehicleManager();
    if (!manager || typeof manager.subscribe !== 'function') {
      return;
    }

    if (typeof vehicleManagerUnsubscribe === 'function') {
      vehicleManagerUnsubscribe();
    }

    vehicleManagerUnsubscribe = manager.subscribe(function (vehicles, meta) {
      if (replayActive) {
        return;
      }

      const sourceLabel = meta && meta.source ? meta.source : 'live';
      updateVehicles(vehicles, { animate: sourceLabel !== 'bootstrap' });
    });
  }

  function buildVehicleFilterCheckboxes() {
    if (!vehicleFiltersListEl || !replayController) {
      return;
    }

    vehicleFiltersListEl.innerHTML = '';
    const vehicles = replayController.getAvailableVehicles();

    vehicles.forEach(vehicleId => {
      const label = document.createElement('label');
      label.className = 'timeline-filter-checkbox';

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = replayController.isVehicleSelected(vehicleId);
      checkbox.value = vehicleId;

      checkbox.addEventListener('change', function () {
        replayController.toggleVehicle(vehicleId);
        replayTimestamps = replayController.getFilteredTimestamps();
        if (timelineRangeEl && replayTimestamps.length) {
          timelineRangeEl.max = replayTimestamps.length - 1;
          replayCursor = Math.min(replayCursor, replayTimestamps.length - 1);
          renderReplayFrame({ animate: false });
        }
      });

      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(` ${vehicleId}`));
      vehicleFiltersListEl.appendChild(label);
    });
  }

  function toggleVehicleFiltersPanel() {
    if (!vehicleFiltersListEl || !vehicleFiltersToggleEl) {
      return;
    }

    const isVisible = vehicleFiltersListEl.style.display !== 'none';
    vehicleFiltersListEl.style.display = isVisible ? 'none' : 'block';
    vehicleFiltersToggleEl.classList.toggle('active', !isVisible);
  }

  function drawVehicleTrail(vehicleId, positions, color) {
    if (!Array.isArray(positions) || positions.length < 2) {
      return;
    }

    const latLngs = positions
      .filter(pos => Array.isArray(pos.currentPosition) && pos.currentPosition.length >= 2)
      .map(pos => [pos.currentPosition[1], pos.currentPosition[0]]);

    if (latLngs.length < 2) {
      return;
    }

    // Remove existing trail if any
    if (vehicleTrails.has(vehicleId)) {
      const existingTrail = vehicleTrails.get(vehicleId);
      if (existingTrail && existingTrail.remove) {
        vehicleLayer.removeLayer(existingTrail);
      }
    }

    // Draw new trail
    const polyline = L.polyline(latLngs, {
      color: color || '#ffb020',
      weight: 2,
      opacity: 0.5,
      lineCap: 'round',
      lineJoin: 'round',
      dashArray: '5, 5',
    });

    polyline.addTo(vehicleLayer);
    vehicleTrails.set(vehicleId, polyline);
  }

  function clearVehicleTrails() {
    vehicleTrails.forEach(trail => {
      if (trail && trail.remove) {
        vehicleLayer.removeLayer(trail);
      }
    });
    vehicleTrails.clear();
  }

  function applyDateFilterReplay() {
    if (!replayController || !dateFromEl || !dateToEl) {
      return;
    }

    setTimelineStatus('Recargando histórico con filtros…');

    const fromDate = dateFromEl.value;
    const toDate = dateToEl.value;

    if (fromDate && toDate && fromDate > toDate) {
      setTimelineStatus('Error: La fecha inicial debe ser anterior a la final');
      return;
    }

    replayController.setDateRange(fromDate || null, toDate || null);
    replayHistory = replayController.getFilteredHistory();
    replayTimestamps = replayController.getFilteredTimestamps();

    if (timelineRangeEl && replayTimestamps.length) {
      timelineRangeEl.max = replayTimestamps.length - 1;
      replayCursor = 0;
      timelineRangeEl.value = 0;
    }

    buildVehicleFilterCheckboxes();
    renderReplayFrame({ animate: false });

    const state = replayController.getFilterState();
    setTimelineStatus(`${state.filteredVehicleCount} vehículos, ${state.filteredTimestampCount} instantes`);
  }

  function bindTimelineControls() {
    if (timelineRangeEl) {
      timelineRangeEl.addEventListener('input', function () {
        if (!replayTimestamps.length) {
          return;
        }

        enterReplayMode();
        seekReplay(Number(this.value), { animate: false });
      });
    }

    if (timelinePlayEl) {
      timelinePlayEl.addEventListener('click', function () {
        toggleReplayPlayback();
      });
    }

    if (timelineLiveEl) {
      timelineLiveEl.addEventListener('click', function () {
        returnToLiveMode();
      });
    }

    // Date filter controls
    if (dateFilterApplyEl) {
      dateFilterApplyEl.addEventListener('click', applyDateFilterReplay);
    }

    // Replay speed control
    if (replaySpeedEl) {
      replaySpeedEl.addEventListener('change', function () {
        if (replayController) {
          replayController.setSpeed(parseFloat(this.value));
        }
      });
    }

    // Vehicle filters toggle
    if (vehicleFiltersToggleEl) {
      vehicleFiltersToggleEl.addEventListener('click', toggleVehicleFiltersPanel);
    }
  }

  function loadTimelineHistory() {
    if (!window.MapApiClient || typeof window.MapApiClient.loadAllVehicleHistory !== 'function') {
      buildReplayIndex([]);
      return Promise.resolve();
    }

    setTimelineStatus('Cargando histórico…');
    return window.MapApiClient.loadAllVehicleHistory({ pageSize: 100 })
      .then(function (history) {
        buildReplayIndex(history && Array.isArray(history.vehicles) ? history.vehicles : []);
      })
      .catch(function (error) {
        console.warn('Unable to load vehicle history:', error);
        buildReplayIndex([]);
      });
  }

  function loadAndRender() {
    setStatus('Cargando datos de movilidad…');

    const mapLoader = window.MapApiClient && typeof window.MapApiClient.loadMapData === 'function'
      ? window.MapApiClient.loadMapData()
      : Promise.resolve(window.MapApiClient ? window.MapApiClient.sampleData() : { routes: [], stops: [], vehicles: [] });

    Promise.allSettled([mapLoader, loadTimelineHistory()])
      .then(function (results) {
        const mapResult = results[0];
        const manager = getVehicleManager();

        if (mapResult.status === 'fulfilled') {
          updateMap(mapResult.value, { fitBounds: true, animate: false });
          if (manager && typeof manager.setVehicles === 'function' && mapResult.value && Array.isArray(mapResult.value.vehicles)) {
            manager.setVehicles(mapResult.value.vehicles, { source: 'bootstrap' });
          }
        } else if (window.MapApiClient && typeof window.MapApiClient.sampleData === 'function') {
          const sampleData = window.MapApiClient.sampleData();
          updateMap(sampleData, { fitBounds: true, animate: false });
          if (manager && typeof manager.setVehicles === 'function' && sampleData && Array.isArray(sampleData.vehicles)) {
            manager.setVehicles(sampleData.vehicles, { source: 'bootstrap' });
          }
          setStatus('Mostrando datos de muestra');
        }

        bindTimelineControls();
        connectVehicleManager();

        if (replayTimestamps.length) {
          setTimelineStatus('Usa la línea temporal para reproducir el histórico');
        }
      })
      .catch(function (error) {
        console.warn('Unable to render map data:', error);
        if (window.MapApiClient && typeof window.MapApiClient.sampleData === 'function') {
          const sampleData = window.MapApiClient.sampleData();
          updateMap(sampleData, { fitBounds: true, animate: false });
          const manager = getVehicleManager();
          if (manager && typeof manager.setVehicles === 'function' && sampleData && Array.isArray(sampleData.vehicles)) {
            manager.setVehicles(sampleData.vehicles, { source: 'bootstrap' });
          }
          connectVehicleManager();
        }
        setStatus('Mostrando datos de muestra');
      });
  }

  window.addEventListener('resize', function () {
    map.invalidateSize();
  });

  window.addEventListener('beforeunload', function () {
    if (typeof vehicleManagerUnsubscribe === 'function') {
      vehicleManagerUnsubscribe();
      vehicleManagerUnsubscribe = null;
    }
    stopReplayPlayback();

    if (animationFrameId !== null) {
      window.cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
  });

  if (detailPanelCloseEl) {
    detailPanelCloseEl.addEventListener('click', clearDetailPanel);
  }

  setPanelEmpty();
  setTimelineControlsDisabled(true);
  setTimelineStatus('Cargando histórico…');

  loadAndRender();
}

if (typeof window !== 'undefined') window.initMap = initMap;
