(function (global) {
  /**
   * Login UI Manager - Handles login form display and user interaction
   */

  const state = {
    isVisible: false,
    isLoading: false,
    error: '',
  };

  const dom = {
    modal: null,
    form: null,
    usernameInput: null,
    passwordInput: null,
    submitButton: null,
    errorMessage: null,
    logoutButton: null,
  };

  /**
   * Initialize the login UI components
   */
  function initialize() {
    // Create modal structure if it doesn't exist
    if (!dom.modal) {
      createModalMarkup();
    }

    // Cache DOM elements
    dom.modal = document.getElementById('login-modal');
    dom.form = document.getElementById('login-form');
    dom.usernameInput = document.getElementById('login-username');
    dom.passwordInput = document.getElementById('login-password');
    dom.submitButton = document.getElementById('login-submit');
    dom.errorMessage = document.getElementById('login-error');
    dom.logoutButton = document.getElementById('logout-button');

    if (!dom.form) {
      console.error('Login form elements not found');
      return;
    }

    // Attach event listeners
    dom.form.addEventListener('submit', handleFormSubmit);
    if (dom.logoutButton) {
      dom.logoutButton.addEventListener('click', handleLogout);
    }

    // Show login if not authenticated
    if (global.AuthManager && !global.AuthManager.isAuthenticated()) {
      show();
    }
  }

  /**
   * Create login modal HTML structure
   */
  function createModalMarkup() {
    const modalHtml = `
      <div id="login-modal" class="login-modal" style="display: none;">
        <div class="login-modal__overlay"></div>
        <div class="login-modal__content">
          <div class="login-modal__card">
            <h1 class="login-modal__title">XDEI P3</h1>
            <p class="login-modal__subtitle">Autenticación de desarrollo</p>
            
            <form id="login-form" class="login-form">
              <div class="login-form__group">
                <label for="login-username" class="login-form__label">Usuario</label>
                <input
                  id="login-username"
                  type="text"
                  class="login-form__input"
                  placeholder="Ingresa tu usuario"
                  required
                  autocomplete="username"
                />
              </div>

              <div class="login-form__group">
                <label for="login-password" class="login-form__label">Contraseña</label>
                <input
                  id="login-password"
                  type="password"
                  class="login-form__input"
                  placeholder="Ingresa tu contraseña"
                  required
                  autocomplete="current-password"
                />
              </div>

              <div id="login-error" class="login-form__error" style="display: none;"></div>

              <button id="login-submit" type="submit" class="login-form__button">
                Iniciar sesión
              </button>
            </form>

            <p class="login-modal__note">
              💡 Para desarrollo: ingresa cualquier usuario y contraseña
            </p>
          </div>
        </div>
      </div>
    `;

    // Insert after body or at the beginning
    const container = document.body || document.documentElement;
    container.insertAdjacentHTML('afterbegin', modalHtml);
  }

  /**
   * Add CSS styles for login modal
   */
  function injectStyles() {
    if (document.getElementById('login-ui-styles')) {
      return; // Already injected
    }

    const style = document.createElement('style');
    style.id = 'login-ui-styles';
    style.textContent = `
      .login-modal {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      }

      .login-modal__overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(2px);
      }

      .login-modal__content {
        position: relative;
        z-index: 1;
        animation: slideUp 0.3s ease-out;
      }

      @keyframes slideUp {
        from {
          opacity: 0;
          transform: translateY(20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      .login-modal__card {
        background: white;
        border-radius: 8px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        padding: 2rem;
        max-width: 400px;
        width: 90%;
      }

      .login-modal__title {
        margin: 0 0 0.5rem 0;
        font-size: 1.5rem;
        font-weight: 600;
        color: #1a1a1a;
      }

      .login-modal__subtitle {
        margin: 0 0 1.5rem 0;
        font-size: 0.875rem;
        color: #666;
      }

      .login-form__group {
        margin-bottom: 1rem;
      }

      .login-form__label {
        display: block;
        margin-bottom: 0.5rem;
        font-size: 0.875rem;
        font-weight: 500;
        color: #333;
      }

      .login-form__input {
        width: 100%;
        padding: 0.75rem;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 1rem;
        box-sizing: border-box;
        transition: border-color 0.2s;
      }

      .login-form__input:focus {
        outline: none;
        border-color: #0b74de;
        box-shadow: 0 0 0 3px rgba(11, 116, 222, 0.1);
      }

      .login-form__input::placeholder {
        color: #999;
      }

      .login-form__error {
        margin: 1rem 0;
        padding: 0.75rem;
        background: #fee;
        border: 1px solid #fcc;
        border-radius: 4px;
        color: #c33;
        font-size: 0.875rem;
      }

      .login-form__button {
        width: 100%;
        padding: 0.75rem;
        background: #0b74de;
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.2s;
      }

      .login-form__button:hover:not(:disabled) {
        background: #0a60b5;
      }

      .login-form__button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }

      .login-modal__note {
        margin: 1rem 0 0 0;
        font-size: 0.8rem;
        color: #999;
        text-align: center;
      }

      .logout-button {
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1000;
        padding: 0.5rem 1rem;
        background: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 0.875rem;
        cursor: pointer;
        transition: background 0.2s;
      }

      .logout-button:hover {
        background: #eee;
      }
    `;

    document.head.appendChild(style);
  }

  /**
   * Handle form submission
   */
  async function handleFormSubmit(e) {
    e.preventDefault();

    if (!global.AuthManager) {
      setError('AuthManager no disponible');
      return;
    }

    const username = (dom.usernameInput?.value || '').trim();
    const password = (dom.passwordInput?.value || '').trim();

    if (!username || !password) {
      setError('Usuario y contraseña requeridos');
      return;
    }

    setLoading(true);
    clearError();

    try {
      const result = await global.AuthManager.login(username, password);

      // Store user ID in localStorage for gamification
      if (window.localStorage) {
        try {
          window.localStorage.setItem('xdei.gamification.userId', result.user_id);
          window.localStorage.setItem('xdei.gamification.displayName', result.user_id);
        } catch (e) {
          console.warn('Failed to store user info:', e);
        }
      }

      // Hide modal and trigger reload
      hide();

      // Dispatch custom event for other components
      const event = new CustomEvent('auth:login', {
        detail: { userId: result.user_id },
      });
      global.dispatchEvent(event);

      // Optional: Reload gamification panel if available
      if (global.GamificationManager && typeof global.GamificationManager.reload === 'function') {
        global.GamificationManager.reload();
      }
    } catch (error) {
      setError(error.message || 'Login falló');
      console.error('Login error:', error);
    } finally {
      setLoading(false);
    }
  }

  /**
   * Handle logout
   */
  function handleLogout() {
    if (global.AuthManager) {
      global.AuthManager.logout();
    }

    // Clear user info from localStorage
    if (window.localStorage) {
      try {
        window.localStorage.removeItem('xdei.gamification.userId');
        window.localStorage.removeItem('xdei.gamification.displayName');
      } catch (e) {
        console.warn('Failed to clear user info:', e);
      }
    }

    // Show login modal again
    show();

    // Dispatch custom event
    const event = new CustomEvent('auth:logout');
    global.dispatchEvent(event);

    // Optional: Clear gamification panel if available
    if (global.GamificationManager && typeof global.GamificationManager.reset === 'function') {
      global.GamificationManager.reset();
    }
  }

  /**
   * Show login modal
   */
  function show() {
    if (!dom.modal) {
      initialize();
    }

    if (dom.modal) {
      dom.modal.style.display = 'flex';
      state.isVisible = true;

      // Focus username input
      if (dom.usernameInput) {
        setTimeout(() => dom.usernameInput.focus(), 100);
      }
    }
  }

  /**
   * Hide login modal
   */
  function hide() {
    if (dom.modal) {
      dom.modal.style.display = 'none';
      state.isVisible = false;
    }
  }

  /**
   * Set loading state
   */
  function setLoading(loading) {
    state.isLoading = loading;
    if (dom.submitButton) {
      dom.submitButton.disabled = loading;
      dom.submitButton.textContent = loading ? 'Iniciando sesión…' : 'Iniciar sesión';
    }
  }

  /**
   * Set error message
   */
  function setError(message) {
    state.error = message;
    if (dom.errorMessage) {
      dom.errorMessage.textContent = message;
      dom.errorMessage.style.display = message ? 'block' : 'none';
    }
  }

  /**
   * Clear error message
   */
  function clearError() {
    setError('');
  }

  /**
   * Add logout button to the UI
   */
  function addLogoutButton() {
    if (document.getElementById('logout-button')) {
      return; // Already exists
    }

    const button = document.createElement('button');
    button.id = 'logout-button';
    button.className = 'logout-button';
    button.textContent = 'Cerrar sesión';
    document.body.appendChild(button);

    button.addEventListener('click', handleLogout);
    dom.logoutButton = button;
  }

  // Initialize styles and UI on load
  function onDOMReady() {
    injectStyles();
    addLogoutButton();
    initialize();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onDOMReady);
  } else {
    onDOMReady();
  }

  // Export API
  global.LoginUI = {
    show,
    hide,
    initialize,
  };
})(window);
