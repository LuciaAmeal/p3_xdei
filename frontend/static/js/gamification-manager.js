(function (global) {
  const STORAGE_USER_ID_KEY = 'xdei.gamification.userId';
  const STORAGE_DISPLAY_NAME_KEY = 'xdei.gamification.displayName';

  const ACHIEVEMENT_CATALOG = [
    {
      id: 'first_trip',
      title: 'Primer viaje',
      description: 'Consigue 10 puntos completando tu primer viaje.',
      icon: '🚌',
      requirementLabel: '10 puntos',
      requirementType: 'points',
      requirementValue: 10,
    },
    {
      id: 'explorer_5',
      title: 'Explorador',
      description: 'Visita 5 paradas distintas para ampliar tu ruta.',
      icon: '🗺️',
      requirementLabel: '5 paradas',
      requirementType: 'stops',
      requirementValue: 5,
    },
    {
      id: 'explorer_10',
      title: 'Explorador avanzado',
      description: 'Visita 10 paradas distintas y domina la red.',
      icon: '🏆',
      requirementLabel: '10 paradas',
      requirementType: 'stops',
      requirementValue: 10,
    },
  ];

  const state = {
    ready: false,
    loading: false,
    redeeming: false,
    userId: '',
    displayName: '',
    profile: null,
    error: '',
    message: '',
  };

  const dom = {
    panel: null,
    body: null,
    status: null,
    userForm: null,
    userIdInput: null,
    displayNameInput: null,
  };

  function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDateTime(value) {
    if (!value) {
      return 'Sin actividad reciente';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return new Intl.DateTimeFormat('es-ES', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
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
      if (!global.localStorage) {
        return;
      }

      if (!value) {
        global.localStorage.removeItem(key);
        return;
      }

      global.localStorage.setItem(key, value);
    } catch (error) {
      // Ignore storage failures in restricted browsers.
    }
  }

  function getCurrentUserId() {
    const globalValue = (global.GAMIFICATION_USER_ID || '').trim();
    if (globalValue) {
      return globalValue;
    }

    const storedValue = getStoredValue(STORAGE_USER_ID_KEY).trim();
    if (storedValue) {
      return storedValue;
    }

    return '';
  }

  function getCurrentDisplayName(userId) {
    const globalValue = (global.GAMIFICATION_DISPLAY_NAME || '').trim();
    if (globalValue) {
      return globalValue;
    }

    const storedValue = getStoredValue(STORAGE_DISPLAY_NAME_KEY).trim();
    if (storedValue) {
      return storedValue;
    }

    return userId;
  }

  function resolveAchievementState(achievement, profile) {
    const isUnlocked = Array.isArray(profile.achievements) && profile.achievements.includes(achievement.id);
    let currentValue = 0;

    if (achievement.requirementType === 'points') {
      currentValue = Number(profile.totalPoints || 0);
    } else if (achievement.requirementType === 'stops') {
      currentValue = Array.isArray(profile.visitedStops) ? profile.visitedStops.length : 0;
    }

    return {
      isUnlocked,
      currentValue,
      progress: achievement.requirementValue
        ? Math.min(100, Math.round((currentValue / achievement.requirementValue) * 100))
        : 0,
    };
  }

  function getNextAchievement(profile) {
    return ACHIEVEMENT_CATALOG.find((achievement) => !resolveAchievementState(achievement, profile).isUnlocked) || null;
  }

  function buildAchievementCard(achievement, profile) {
    const status = resolveAchievementState(achievement, profile);
    const statusLabel = status.isUnlocked ? 'Desbloqueado' : 'Bloqueado';
    const progressText = status.isUnlocked
      ? 'Completado'
      : `${status.currentValue}/${achievement.requirementValue} ${achievement.requirementType === 'points' ? 'puntos' : 'paradas'}`;

    return `
      <article class="gamification-achievement ${status.isUnlocked ? 'gamification-achievement--unlocked' : ''}">
        <div class="gamification-achievement__icon" aria-hidden="true">${escapeHtml(achievement.icon)}</div>
        <div class="gamification-achievement__content">
          <div class="gamification-achievement__meta">
            <h4 class="gamification-achievement__title">${escapeHtml(achievement.title)}</h4>
            <span class="gamification-achievement__badge">${escapeHtml(statusLabel)}</span>
          </div>
          <p class="gamification-achievement__description">${escapeHtml(achievement.description)}</p>
          <div class="gamification-achievement__progress">
            <div class="gamification-achievement__progress-track" aria-hidden="true">
              <span style="width:${status.progress}%"></span>
            </div>
            <span class="gamification-achievement__progress-label">${escapeHtml(progressText)}</span>
          </div>
          <div class="gamification-achievement__requirement">Requisito: ${escapeHtml(achievement.requirementLabel)}</div>
        </div>
      </article>
    `;
  }

  function buildRedeemedItem(discount) {
    return `
      <li class="gamification-history__item">
        <div class="gamification-history__row">
          <strong>${escapeHtml(discount.discountCode || 'Canje')}</strong>
          <span>${escapeHtml(discount.status || 'redeemed')}</span>
        </div>
        <div class="gamification-history__meta">
          Descuento: ${escapeHtml(discount.discountValue ?? 0)}
        </div>
        <div class="gamification-history__meta">Canjeado: ${escapeHtml(formatDateTime(discount.redeemedAt))}</div>
        ${discount.validUntil ? `<div class="gamification-history__meta">Válido hasta: ${escapeHtml(formatDateTime(discount.validUntil))}</div>` : ''}
      </li>
    `;
  }

  function renderLoading() {
    return `
      <section class="gamification-section gamification-section--loading" aria-busy="true">
        <div class="gamification-skeleton gamification-skeleton--title"></div>
        <div class="gamification-skeleton gamification-skeleton--line"></div>
        <div class="gamification-skeleton gamification-skeleton--line"></div>
        <div class="gamification-skeleton gamification-skeleton--card"></div>
        <div class="gamification-skeleton gamification-skeleton--card"></div>
      </section>
    `;
  }

  function renderEmpty() {
    return `
      <section class="gamification-section gamification-empty">
        <h3 class="gamification-section__title">Carga tu perfil</h3>
        <p class="gamification-empty__text">Introduce un usuario para ver sus puntos, logros y canjes disponibles.</p>
      </section>
    `;
  }

  function renderError() {
    return `
      <section class="gamification-section gamification-error" role="alert">
        <h3 class="gamification-section__title">No se pudo cargar el perfil</h3>
        <p class="gamification-empty__text">${escapeHtml(state.error || 'Error desconocido')}</p>
      </section>
    `;
  }

  function renderProfile(profile) {
    const unlockedAchievements = Array.isArray(profile.achievements) ? profile.achievements : [];
    const visitedStops = Array.isArray(profile.visitedStops) ? profile.visitedStops : [];
    const redeemedDiscounts = Array.isArray(profile.redeemedDiscounts) ? profile.redeemedDiscounts : [];
    const nextAchievement = getNextAchievement(profile);
    const nextAchievementStatus = nextAchievement ? resolveAchievementState(nextAchievement, profile) : null;
    const nextProgressText = nextAchievement
      ? `${nextAchievementStatus.currentValue}/${nextAchievement.requirementValue} ${nextAchievement.requirementType === 'points' ? 'puntos' : 'paradas'}`
      : 'Todos los logros desbloqueados';

    return `
      <section class="gamification-section">
        <div class="gamification-summary">
          <div class="gamification-summary__card">
            <span class="gamification-summary__label">Puntos</span>
            <strong class="gamification-summary__value">${escapeHtml(profile.totalPoints || 0)}</strong>
          </div>
          <div class="gamification-summary__card">
            <span class="gamification-summary__label">Logros</span>
            <strong class="gamification-summary__value">${escapeHtml(unlockedAchievements.length)}</strong>
          </div>
          <div class="gamification-summary__card">
            <span class="gamification-summary__label">Paradas</span>
            <strong class="gamification-summary__value">${escapeHtml(visitedStops.length)}</strong>
          </div>
          <div class="gamification-summary__card">
            <span class="gamification-summary__label">Canjes</span>
            <strong class="gamification-summary__value">${escapeHtml(redeemedDiscounts.length)}</strong>
          </div>
        </div>
      </section>

      <section class="gamification-section">
        <h3 class="gamification-section__title">Progreso</h3>
        <div class="gamification-progress">
          <div class="gamification-progress__header">
            <span>${escapeHtml(nextAchievement ? nextAchievement.title : 'Ruta completada')}</span>
            <span>${escapeHtml(nextProgressText)}</span>
          </div>
          <div class="gamification-progress__track" aria-hidden="true">
            <span style="width:${escapeHtml(nextAchievementStatus ? nextAchievementStatus.progress : 100)}%"></span>
          </div>
          <p class="gamification-progress__hint">
            ${escapeHtml(nextAchievement ? nextAchievement.description : 'Ya has desbloqueado todos los hitos disponibles en esta versión.')}
          </p>
        </div>
      </section>

      <section class="gamification-section">
        <h3 class="gamification-section__title">Logros</h3>
        <div class="gamification-achievement-grid">
          ${ACHIEVEMENT_CATALOG.map((achievement) => buildAchievementCard(achievement, profile)).join('')}
        </div>
      </section>

      <section class="gamification-section">
        <h3 class="gamification-section__title">Canjear puntos</h3>
        <form id="gamification-redeem-form" class="gamification-form">
          <div class="gamification-form__grid">
            <label class="gamification-field">
              <span>Código</span>
              <input name="discountCode" type="text" placeholder="BUS10" required />
            </label>
            <label class="gamification-field">
              <span>Valor descuento</span>
              <input name="discountValue" type="number" min="0" step="1" placeholder="10" />
            </label>
            <label class="gamification-field">
              <span>Coste en puntos</span>
              <input name="pointsCost" type="number" min="1" step="1" placeholder="12" required />
            </label>
            <label class="gamification-field">
              <span>Válido hasta</span>
              <input name="validUntil" type="datetime-local" />
            </label>
          </div>
          <button class="gamification-button" type="submit" ${state.redeeming ? 'disabled' : ''}>${state.redeeming ? 'Canjeando…' : 'Canjear descuento'}</button>
        </form>
      </section>

      <section class="gamification-section">
        <h3 class="gamification-section__title">Historial de canjes</h3>
        ${redeemedDiscounts.length
          ? `<ul class="gamification-history">${redeemedDiscounts.map((discount) => buildRedeemedItem(discount)).join('')}</ul>`
          : '<p class="gamification-empty__text">Aún no has realizado canjes.</p>'}
      </section>
    `;
  }

  function renderStatusText() {
    if (state.loading) {
      return 'Cargando perfil…';
    }

    if (state.redeeming) {
      return 'Procesando canje…';
    }

    if (state.message) {
      return state.message;
    }

    if (state.error) {
      return 'Perfil con incidencias';
    }

    return state.profile ? `Perfil listo · ${state.userId}` : 'Listo para cargar';
  }

  function render() {
    if (!dom.panel || !dom.body || !dom.status) {
      return;
    }

    dom.status.textContent = renderStatusText();
    dom.panel.classList.toggle('gamification-panel--loading', Boolean(state.loading));
    dom.panel.classList.toggle('gamification-panel--error', Boolean(state.error));

    let content = '';
    if (state.loading) {
      content = renderLoading();
    } else if (state.error) {
      content = renderError();
    } else if (!state.profile) {
      content = renderEmpty();
    } else {
      content = renderProfile(state.profile);
    }

    dom.body.innerHTML = `
      <section class="gamification-section">
        <form id="gamification-user-form" class="gamification-user-form" autocomplete="off">
          <label class="gamification-field">
            <span>Usuario</span>
            <input id="gamification-user-id" name="userId" type="text" placeholder="alice" value="${escapeHtml(state.userId)}" required />
          </label>
          <label class="gamification-field">
            <span>Nombre</span>
            <input id="gamification-display-name" name="displayName" type="text" placeholder="Alice" value="${escapeHtml(state.displayName)}" />
          </label>
          <button class="gamification-button gamification-button--ghost" type="submit">Cargar perfil</button>
        </form>
      </section>
      ${state.message ? `<section class="gamification-section gamification-message" role="status">${escapeHtml(state.message)}</section>` : ''}
      ${content}
    `;

    dom.userForm = dom.body.querySelector('#gamification-user-form');
    dom.userIdInput = dom.body.querySelector('#gamification-user-id');
    dom.displayNameInput = dom.body.querySelector('#gamification-display-name');
  }

  async function loadProfile(userId, displayName) {
    const resolvedUserId = String(userId || '').trim();
    if (!resolvedUserId) {
      state.error = 'Debes indicar un usuario.';
      state.profile = null;
      state.loading = false;
      state.message = '';
      render();
      return;
    }

    state.loading = true;
    state.error = '';
    state.message = '';
    state.userId = resolvedUserId;
    state.displayName = String(displayName || '').trim() || resolvedUserId;
    render();

    setStoredValue(STORAGE_USER_ID_KEY, state.userId);
    setStoredValue(STORAGE_DISPLAY_NAME_KEY, state.displayName);

    try {
      const profile = await global.MapApiClient.loadGamificationProfile(state.userId, {
        displayName: state.displayName,
      });
      state.profile = profile;
      state.message = `Perfil cargado: ${profile.displayName || state.displayName}`;
    } catch (error) {
      state.profile = null;
      state.error = error && error.message ? error.message : 'No se pudo cargar el perfil';
    } finally {
      state.loading = false;
      render();
    }
  }

  async function submitRedeem(formElement) {
    const formData = new FormData(formElement);
    const discountCode = String(formData.get('discountCode') || '').trim();
    const discountValueRaw = String(formData.get('discountValue') || '').trim();
    const pointsCostRaw = String(formData.get('pointsCost') || '').trim();
    const validUntilRaw = String(formData.get('validUntil') || '').trim();

    if (!discountCode) {
      state.error = 'El código de descuento es obligatorio.';
      render();
      return;
    }

    state.redeeming = true;
    state.error = '';
    state.message = '';
    render();

    try {
      const validUntil = validUntilRaw ? new Date(validUntilRaw) : null;
      const result = await global.MapApiClient.redeemDiscount({
        userId: state.userId,
        displayName: state.displayName,
        discountCode,
        discountValue: discountValueRaw ? Number(discountValueRaw) : 0,
        pointsCost: pointsCostRaw ? Number(pointsCostRaw) : undefined,
        validUntil: validUntil && !Number.isNaN(validUntil.getTime()) ? validUntil.toISOString() : undefined,
      });

      state.profile = result.profile;
      state.message = `Canje realizado: ${result.redemption.discountCode}`;
      formElement.reset();
    } catch (error) {
      state.error = error && error.message ? error.message : 'No se pudo canjear el descuento';
    } finally {
      state.redeeming = false;
      render();
    }
  }

  function handlePanelSubmit(event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }

    if (form.id === 'gamification-user-form') {
      event.preventDefault();
      const userId = form.querySelector('#gamification-user-id')?.value || '';
      const displayName = form.querySelector('#gamification-display-name')?.value || '';
      loadProfile(userId, displayName);
      return;
    }

    if (form.id === 'gamification-redeem-form') {
      event.preventDefault();
      submitRedeem(form);
    }
  }

  function hydrateStateFromStorage() {
    state.userId = getCurrentUserId();
    state.displayName = getCurrentDisplayName(state.userId);
  }

  function init() {
    if (state.ready) {
      return;
    }

    dom.panel = document.getElementById('gamification-panel');
    dom.body = document.getElementById('gamification-panel-body');
    dom.status = document.getElementById('gamification-status');

    if (!dom.panel || !dom.body || !dom.status) {
      return;
    }

    hydrateStateFromStorage();
    dom.panel.addEventListener('submit', handlePanelSubmit);
    state.ready = true;
    render();

    if (state.userId) {
      loadProfile(state.userId, state.displayName);
    }
  }

  function refresh() {
    if (!state.userId) {
      return Promise.resolve();
    }

    return loadProfile(state.userId, state.displayName);
  }

  function setUser(userId, displayName) {
    state.userId = String(userId || '').trim();
    state.displayName = String(displayName || '').trim() || state.userId;
    setStoredValue(STORAGE_USER_ID_KEY, state.userId);
    setStoredValue(STORAGE_DISPLAY_NAME_KEY, state.displayName);
    render();
  }

  global.GamificationManager = {
    init,
    refresh,
    setUser,
    loadProfile,
    getState: function () {
      return {
        ready: state.ready,
        loading: state.loading,
        redeeming: state.redeeming,
        userId: state.userId,
        displayName: state.displayName,
        profile: state.profile,
        error: state.error,
        message: state.message,
      };
    },
  };

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})(window);
