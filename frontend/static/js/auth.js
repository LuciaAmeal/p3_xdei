(function (global) {
  function initAuth() {
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const btnGuest = document.getElementById('btn-guest');
    const btnCreate = document.getElementById('btn-create');

    if (loginForm) {
      loginForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const username = loginForm.username.value;
        const password = loginForm.password.value;

        if (username === 'admin' && password === 'admin') {
          const mainMenu = document.getElementById('main-menu');
          if (mainMenu) {
            mainMenu.hidden = false;
          }
          if (global.TabManager) {
            global.TabManager.setTab('2d');
          }
        } else {
          if (loginError) {
            loginError.hidden = false;
          }
        }
      });
    }

    // Listen for logout (returning to login tab)
    global.addEventListener('xdei:tab-changed', function (event) {
      const detail = (event && event.detail) || {};
      if (detail.tab === 'login') {
        const mainMenu = document.getElementById('main-menu');
        if (mainMenu) {
          mainMenu.hidden = true;
        }
      }
    });

    if (btnGuest) {
      btnGuest.addEventListener('click', function () {
        alert("datos de prueba, todavía no se permite continuar como invitado, usuario y contraseña son admin");
      });
    }

    if (btnCreate) {
      btnCreate.addEventListener('click', function () {
        alert("datos de prueba, todavía no se permite crear usuario, usuario y contraseña son admin");
      });
    }
  }

  if (document.readyState === 'loading') {
    global.addEventListener('DOMContentLoaded', initAuth, { once: true });
  } else {
    initAuth();
  }
})(window);
