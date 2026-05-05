(function (global) {
  /**
   * Authentication Manager - Handles JWT token storage and retrieval
   * Stores JWT in localStorage and provides helper methods for auth operations
   */

  const STORAGE_TOKEN_KEY = 'xdei.auth.token';

  /**
   * Store JWT token in localStorage
   * @param {string} token - JWT token string
   */
  function setToken(token) {
    try {
      if (!global.localStorage) {
        console.warn('localStorage not available');
        return;
      }

      if (!token) {
        global.localStorage.removeItem(STORAGE_TOKEN_KEY);
        return;
      }

      global.localStorage.setItem(STORAGE_TOKEN_KEY, token);
    } catch (error) {
      console.error('Failed to store token:', error);
    }
  }

  /**
   * Retrieve JWT token from localStorage
   * @returns {string|null} JWT token or null if not found
   */
  function getToken() {
    try {
      return global.localStorage ? global.localStorage.getItem(STORAGE_TOKEN_KEY) || null : null;
    } catch (error) {
      console.error('Failed to retrieve token:', error);
      return null;
    }
  }

  /**
   * Check if user is authenticated (has valid token)
   * @returns {boolean} true if token exists
   */
  function isAuthenticated() {
    return Boolean(getToken());
  }

  /**
   * Clear authentication (logout)
   */
  function logout() {
    try {
      if (global.localStorage) {
        global.localStorage.removeItem(STORAGE_TOKEN_KEY);
      }
    } catch (error) {
      console.error('Failed to logout:', error);
    }
  }

  /**
   * Perform login with credentials
   * @param {string} username - Username
   * @param {string} password - Password
   * @returns {Promise} Resolves with {token, user_id, expires_in_hours} or rejects with error
   */
  async function login(username, password) {
    const backendUrl = resolveBackendBaseUrl();

    if (!backendUrl) {
      return Promise.reject(new Error('Backend URL not available'));
    }

    try {
      const response = await fetch(`${backendUrl}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: String(username || '').trim(),
          password: String(password || '').trim(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Login failed: ${response.statusText}`);
      }

      const data = await response.json();

      if (!data.token) {
        throw new Error('No token received from server');
      }

      // Store token
      setToken(data.token);

      return {
        token: data.token,
        user_id: data.user_id,
        expires_in_hours: data.expires_in_hours,
      };
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  /**
   * Resolve backend base URL from window context or defaults
   * @returns {string} Backend base URL
   */
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

  // Export API
  global.AuthManager = {
    login,
    logout,
    setToken,
    getToken,
    isAuthenticated,
  };
})(window);
