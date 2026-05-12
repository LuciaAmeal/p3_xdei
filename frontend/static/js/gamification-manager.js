(function (global) {
  const STORAGE_USER_ID_KEY = 'xdei.gamification.userId';
  const STORAGE_DISPLAY_NAME_KEY = 'xdei.gamification.displayName';

  const ACHIEVEMENT_CATALOG = [
    { id: 'first_trip', title: 'Iniciación', description: 'Completa tu primer viaje en transporte público.', icon: '🎫', requirementType: 'points', requirementValue: 10 },
    { id: 'explorer_3', title: 'Explorador Novato', description: 'Visita 3 paradas diferentes de la ciudad.', icon: '🗺️', requirementType: 'stops', requirementValue: 3 },
    { id: 'explorer_6', title: 'Maestro de Rutas', description: 'Has visitado todas las paradas de la red actual.', icon: '🏆', requirementType: 'stops', requirementValue: 6 },
    { id: 'zone_centro', title: 'Conquistador del Centro', description: 'Has visitado todas las paradas de la Zona Centro.', icon: '🏛️', requirementType: 'zone', zoneId: 'Centro', stops: ['urn:ngsi-ld:GtfsStop:s1', 'urn:ngsi-ld:GtfsStop:s2'] },
    { id: 'zone_puerto', title: 'Lobo de Mar', description: 'Has visitado todas las paradas de la Zona Puerto.', icon: '⚓', requirementType: 'zone', zoneId: 'Puerto', stops: ['urn:ngsi-ld:GtfsStop:s3', 'urn:ngsi-ld:GtfsStop:s4'] },
    { id: 'zone_riazor', title: 'Sabor a Sal', description: 'Has visitado todas las paradas de la Zona Riazor.', icon: '🌊', requirementType: 'zone', zoneId: 'Riazor', stops: ['urn:ngsi-ld:GtfsStop:s5', 'urn:ngsi-ld:GtfsStop:s6'] },
    { id: 'points_500', title: 'Ahorrador Sostenible', description: 'Acumula 500 puntos de movilidad.', icon: '💰', requirementType: 'points', requirementValue: 500 },
  ];

  const ZONES = [
    { id: 'Centro', name: 'Zona Centro', color: '#10b981', coords: [[43.368, -8.415], [43.372, -8.410], [43.370, -8.405], [43.365, -8.408]] },
    { id: 'Puerto', name: 'Zona Puerto', color: '#3b82f6', coords: [[43.360, -8.400], [43.365, -8.395], [43.360, -8.390], [43.355, -8.395]] },
    { id: 'Riazor', name: 'Zona Riazor', color: '#f59e0b', coords: [[43.365, -8.425], [43.370, -8.420], [43.368, -8.415], [43.362, -8.420]] },
  ];

  const state = {
    ready: false,
    loading: false,
    userId: '',
    displayName: '',
    profile: null,
    error: '',
    map: null,
    allStops: [],
  };

  const dom = {
    panel: null,
    body: null,
    status: null,
  };

  function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getStoredValue(key) {
    try {
      return global.localStorage ? global.localStorage.getItem(key) || '' : '';
    } catch (error) {
      return '';
    }
  }

  function setStoredValue(key, value) {
    try {
      if (global.localStorage) {
        if (!value) global.localStorage.removeItem(key);
        else global.localStorage.setItem(key, value);
      }
    } catch (error) {}
  }

  function getCurrentUserId() {
    return getStoredValue(STORAGE_USER_ID_KEY).trim() || 'admin';
  }

  function getCurrentDisplayName(userId) {
    const stored = getStoredValue(STORAGE_DISPLAY_NAME_KEY).trim();
    if (stored) return stored;
    return userId === 'admin' ? 'Administrador' : userId;
  }

  function resolveAchievementState(achievement, profile) {
    if (!profile) return { isUnlocked: false, progress: 0 };
    const visitedStops = Array.isArray(profile.visitedStops) ? profile.visitedStops : [];
    let isUnlocked = Array.isArray(profile.achievements) && profile.achievements.includes(achievement.id);
    let currentValue = 0;
    let requirementValue = achievement.requirementValue || 0;

    if (achievement.requirementType === 'points') {
      currentValue = Number(profile.totalPoints || 0);
    } else if (achievement.requirementType === 'stops') {
      currentValue = visitedStops.length;
    } else if (achievement.requirementType === 'zone') {
      const zoneStops = achievement.stops || [];
      const visitedInZone = zoneStops.filter(s => visitedStops.includes(s));
      currentValue = visitedInZone.length;
      requirementValue = zoneStops.length;
      if (currentValue >= requirementValue) isUnlocked = true;
    }

    return {
      isUnlocked,
      currentValue,
      requirementValue,
      progress: requirementValue > 0 ? Math.min(100, (currentValue / requirementValue) * 100) : 100
    };
  }

  function isZoneUnlocked(zone, visitedStops) {
    const zoneAchievement = ACHIEVEMENT_CATALOG.find(a => a.requirementType === 'zone' && a.zoneId === zone.id);
    if (!zoneAchievement) return false;
    return zoneAchievement.stops.every(s => visitedStops.includes(s));
  }

  function renderAchievementCard(achievement, profile) {
    const status = resolveAchievementState(achievement, profile);
    return `
      <div class="gamification-achievement-card ${status.isUnlocked ? 'is-unlocked' : ''}">
        <div class="gamification-achievement-icon">${achievement.icon}</div>
        <div style="flex: 1;">
          <div class="gamification-achievement-name">${escapeHtml(achievement.title)}</div>
          <div class="gamification-achievement-desc">${escapeHtml(achievement.description)}</div>
          <div style="margin-top: 0.75rem; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
            <div style="width: ${status.progress}%; height: 100%; background: #10b981; box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);"></div>
          </div>
        </div>
        <div class="gamification-achievement-badge">
          ${status.isUnlocked ? 'Completado' : `${status.currentValue}/${status.requirementValue}`}
        </div>
      </div>
    `;
  }

  function renderProfile(profile) {
    const visitedStops = Array.isArray(profile.visitedStops) ? profile.visitedStops : [];
    const unlockedAchievements = ACHIEVEMENT_CATALOG.filter(a => resolveAchievementState(a, profile).isUnlocked);
    const unlockedZones = ZONES.filter(z => isZoneUnlocked(z, visitedStops));

    return `
      <div class="gamification-dashboard-main">
        <div class="gamification-stats-grid">
          <div class="gamification-stat-card">
            <span class="gamification-stat-card__label">Puntos Totales</span>
            <span class="gamification-stat-card__value">${profile.totalPoints || 0}</span>
          </div>
          <div class="gamification-stat-card">
            <span class="gamification-stat-card__label">Paradas Visitadas</span>
            <span class="gamification-stat-card__value">${visitedStops.length}</span>
          </div>
          <div class="gamification-stat-card">
            <span class="gamification-stat-card__label">Logros Desbloqueados</span>
            <span class="gamification-stat-card__value">${unlockedAchievements.length}</span>
          </div>
          <div class="gamification-stat-card">
            <span class="gamification-stat-card__label">Zonas Dominadas</span>
            <span class="gamification-stat-card__value">${unlockedZones.length} / ${ZONES.length}</span>
          </div>
        </div>

        <div class="gamification-achievement-section">
          <h3 class="gamification-section__title" style="margin: 2rem 0 1.5rem; font-size: 1.5rem;">Tus Logros y Objetivos</h3>
          <div class="gamification-achievement-grid">
            ${ACHIEVEMENT_CATALOG.map(a => renderAchievementCard(a, profile)).join('')}
          </div>
        </div>
      </div>

      <div class="gamification-dashboard-side">
        <div class="gamification-ranking-card">
          <h3 class="gamification-ranking-title">Ranking Global</h3>
          <div class="gamification-ranking-list">
            <div class="gamification-ranking-row is-user">
              <span class="gamification-rank-number">#1</span>
              <span class="gamification-rank-name">Tú (${escapeHtml(profile.displayName || profile.userId)})</span>
              <span class="gamification-rank-points">${profile.totalPoints || 0}</span>
            </div>
            <div class="gamification-ranking-row">
              <span class="gamification-rank-number">#2</span>
              <span class="gamification-rank-name">EcoViajero Coruña</span>
              <span class="gamification-rank-points">450</span>
            </div>
            <div class="gamification-ranking-row">
              <span class="gamification-rank-number">#3</span>
              <span class="gamification-rank-name">BusMaster88</span>
              <span class="gamification-rank-points">210</span>
            </div>
          </div>
        </div>

        <div class="gamification-stat-card" style="margin-top: auto;">
          <h3 class="gamification-section__title" style="font-size: 1rem; margin-bottom: 1rem;">Configuración de Perfil</h3>
          <form id="gamification-user-form" class="gamification-user-form">
            <div style="display: grid; gap: 1rem;">
              <label class="gamification-field">
                <span>ID Usuario</span>
                <input id="gamification-user-id" name="userId" type="text" value="${escapeHtml(profile.userId)}" required />
              </label>
              <label class="gamification-field">
                <span>Nombre</span>
                <input id="gamification-display-name" name="displayName" type="text" value="${escapeHtml(profile.displayName || '')}" />
              </label>
              <button class="gamification-button" type="submit" style="background: #10b981; color: #fff; font-weight: 700; padding: 0.8rem; border-radius: 12px; border: none; cursor: pointer;">Actualizar</button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  function initMap() {
    const container = document.getElementById('gamification-map');
    if (!container || typeof L === 'undefined') return;
    
    if (state.map) {
      state.map.remove();
      state.map = null;
    }

    const map = L.map(container, {
      zoomControl: false,
      attributionControl: false
    }).setView([43.365, -8.410], 14);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png').addTo(map);

    const visitedStops = state.profile ? state.profile.visitedStops : [];

    // Draw Zones
    ZONES.forEach(zone => {
      const isUnlocked = isZoneUnlocked(zone, visitedStops);
      const poly = L.polygon(zone.coords, {
        color: zone.color,
        fillColor: zone.color,
        fillOpacity: isUnlocked ? 0.3 : 0.05,
        weight: isUnlocked ? 2 : 1,
        dashArray: isUnlocked ? null : '5, 5'
      }).addTo(map);
      
      poly.bindTooltip(`${zone.name} ${isUnlocked ? '✅' : '🔒'}`, { sticky: true });
    });

    // Draw Stop Markers
    if (Array.isArray(state.allStops)) {
      state.allStops.forEach(stop => {
        if (!stop.location) return;
        const isVisited = visitedStops.includes(stop.id);
        L.circleMarker([stop.location[1], stop.location[0]], {
          radius: isVisited ? 6 : 4,
          fillColor: isVisited ? '#10b981' : '#4b5563',
          color: '#000',
          weight: 1,
          fillOpacity: isVisited ? 1 : 0.5
        }).addTo(map).bindPopup(`<strong>${escapeHtml(stop.stopName)}</strong><br>${isVisited ? 'Visitada' : 'No visitada'}`);
      });
    }

    state.map = map;
  }

  function render() {
    if (!dom.body) return;
    
    if (state.loading) {
      dom.body.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 1.5rem; color: #a1a1aa;">Cargando tu progreso sostenible...</div>';
      return;
    }

    if (state.error) {
      dom.body.innerHTML = `<div style="padding: 2rem; color: #ef4444; text-align: center;"><h3>Error al cargar perfil</h3><p>${escapeHtml(state.error)}</p><button onclick="GamificationManager.init()" style="margin-top: 1rem; padding: 0.5rem 1rem; background: #10b981; color: #fff; border: none; border-radius: 8px; cursor: pointer;">Reintentar</button></div>`;
      return;
    }

    if (state.profile) {
      dom.body.innerHTML = renderProfile(state.profile);
      const form = dom.body.querySelector('#gamification-user-form');
      if (form) form.addEventListener('submit', handlePanelSubmit);
      
      // Delay map initialization to ensure DOM is ready and container has size
      // setTimeout(initMap, 200); // Dishabilitado por ahora a petición del usuario
    } else {
      dom.body.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 1.5rem; color: #a1a1aa;">Inicia sesión para ver tu progreso.</div>';
    }
  }

  async function loadProfile(userId, displayName) {
    if (!userId) return;
    state.loading = true;
    state.error = '';
    render();

    try {
      if (!global.MapApiClient) {
        throw new Error('API Client no disponible');
      }

      if (state.allStops.length === 0) {
        const stopsData = await global.MapApiClient.loadStops();
        state.allStops = stopsData.stops || [];
      }
      
      const profile = await global.MapApiClient.loadGamificationProfile(userId, { displayName });
      state.profile = profile;
      state.userId = userId;
      state.displayName = profile.displayName || displayName;
      
      setStoredValue(STORAGE_USER_ID_KEY, userId);
      setStoredValue(STORAGE_DISPLAY_NAME_KEY, state.displayName);
    } catch (e) {
      console.error('Gamification error:', e);
      state.error = e.message || 'Error desconocido';
    } finally {
      state.loading = false;
      render();
    }
  }

  function handlePanelSubmit(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const userId = formData.get('userId');
    const displayName = formData.get('displayName');
    if (userId) loadProfile(userId, displayName);
  }

  function init() {
    dom.panel = document.getElementById('gamification-panel');
    dom.body = document.getElementById('gamification-panel-body');
    dom.status = document.getElementById('gamification-status');
    
    if (!dom.panel || !dom.body) {
      console.warn('Gamification elements not found');
      return;
    }

    const userId = getCurrentUserId();
    const displayName = getCurrentDisplayName(userId);
    loadProfile(userId, displayName);
  }

  global.GamificationManager = { init };
  
  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})(window);
