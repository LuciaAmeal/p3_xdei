(function (global) {
  const DEFAULT_TAB = 'login';
  const MOBILE_MEDIA_QUERY = '(max-width: 768px)';

  const state = {
    activeTab: DEFAULT_TAB,
    activeView: '2d',
  };

  const dom = {
    buttons: [],
    panels: [],
    menu: null,
    menuToggle: null,
  };

  function isMobile() {
    return typeof global.matchMedia === 'function' && global.matchMedia(MOBILE_MEDIA_QUERY).matches;
  }

  function getButtons() {
    return Array.from(document.querySelectorAll('[data-tab-target]'));
  }

  function getPanels() {
    return Array.from(document.querySelectorAll('[data-tab-panel]'));
  }

  function setBodyState() {
    document.body.setAttribute('data-active-tab', state.activeTab);
    document.body.setAttribute('data-active-view', state.activeView);
  }

  function updateButtons() {
    dom.buttons.forEach((button) => {
      const target = button.getAttribute('data-tab-target');
      const selected = target === state.activeTab;
      button.classList.toggle('is-active', selected);
      button.setAttribute('aria-selected', selected ? 'true' : 'false');
    });
  }

  function updatePanels() {
    const mobile = isMobile();
    const isMapView = state.activeTab === '2d' || state.activeTab === '3d';

    dom.panels.forEach((panel) => {
      const panelName = panel.getAttribute('data-tab-panel');

      if (mobile) {
        panel.hidden = panelName !== state.activeTab;
      } else {
        if (panelName === '2d' || panelName === '3d') {
          // Only show maps if the active tab IS a map view
          panel.hidden = !isMapView || (panelName !== state.activeView);
        } else {
          // Other panels (login, prediction, gamification)
          panel.hidden = panelName !== state.activeTab;
        }
      }
    });
  }

  function emitEvent(name, detail) {
    global.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
  }

  function setTab(nextTab, options) {
    const config = options || {};
    if (!nextTab) {
      return;
    }

    state.activeTab = nextTab;
    if (nextTab === '3d' || nextTab === '2d') {
      state.activeView = nextTab;
    }

    setBodyState();
    updateButtons();
    updatePanels();

    if (config.emit !== false) {
      emitEvent('xdei:tab-changed', {
        tab: state.activeTab,
        view: state.activeView,
      });
    }
  }

  function setView(nextView, options) {
    const config = options || {};
    if (nextView !== '3d' && nextView !== '2d') {
      return;
    }

    state.activeView = nextView;
    if (state.activeTab === '3d' || state.activeTab === '2d') {
      state.activeTab = nextView;
    }

    setBodyState();
    updateButtons();
    updatePanels();

    if (config.emit !== false) {
      emitEvent('xdei:view-changed', {
        tab: state.activeTab,
        view: state.activeView,
      });
    }
  }

  function bindEvents() {
    dom.buttons.forEach((button) => {
      button.addEventListener('click', function () {
        const target = button.getAttribute('data-tab-target');
        if (!target) {
          return;
        }

        setTab(target);
        
        // Always close menu after selection
        if (dom.menu) {
          dom.menu.classList.remove('is-open');
        }
      });
    });

    if (dom.menuToggle && dom.menu) {
      dom.menuToggle.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dom.menu.classList.toggle('is-open');
      });

      document.addEventListener('click', function () {
        dom.menu.classList.remove('is-open');
      });
    }

    global.addEventListener('resize', function () {
      updatePanels();
    });

    global.addEventListener('xdei:set-view', function (event) {
      const detail = (event && event.detail) || {};
      setView(detail.view || '3d');
    });
  }

  function init() {
    dom.buttons = getButtons();
    dom.panels = getPanels();
    dom.menu = document.getElementById('main-menu');
    dom.menuToggle = document.getElementById('menu-toggle');

    if (!dom.buttons.length || !dom.panels.length) {
      return;
    }

    setBodyState();
    updateButtons();
    updatePanels();
    bindEvents();

    emitEvent('xdei:tab-changed', {
      tab: state.activeTab,
      view: state.activeView,
    });
  }

  global.TabManager = {
    init: init,
    setTab: setTab,
    setView: setView,
    getState: function () {
      return {
        activeTab: state.activeTab,
        activeView: state.activeView,
      };
    },
  };

  if (document.readyState === 'loading') {
    global.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})(window);
