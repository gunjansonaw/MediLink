import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

/**
 * Central Axios instance for all MediLink API calls.
 *
 * Tokens are stored in HttpOnly cookies managed by the Django backend —
 * JavaScript never reads or writes them directly.
 * `withCredentials: true` tells the browser to include those cookies on
 * every cross-origin request automatically.
 */
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,          // send/receive cookies on every request
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor ────────────────────────────────────────────────────
// We no longer need to manually attach Authorization headers because the
// cookie is sent automatically by the browser.  We still add the CSRF
// header for mutating requests (Django's CsrfViewMiddleware validates it).
api.interceptors.request.use(
  (config) => {
    // Read the CSRF token from the cookie Django sets (csrftoken)
    const csrfToken = getCookie('csrftoken');
    if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(config.method)) {
      config.headers['X-CSRFToken'] = csrfToken;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ── Response interceptor ───────────────────────────────────────────────────
// On a 401 response, silently attempt to refresh the access token via the
// refresh cookie, then replay the original request once.
let isRefreshing = false;
let refreshSubscribers = [];

function onRefreshed() {
  refreshSubscribers.forEach((cb) => cb());
  refreshSubscribers = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/users/token/refresh/') &&
      !originalRequest.url?.includes('/users/login/')
    ) {
      if (isRefreshing) {
        // Queue requests while a refresh is in-flight
        return new Promise((resolve, reject) => {
          refreshSubscribers.push(() => {
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Hit our cookie-based refresh endpoint; the browser sends the
        // refresh cookie automatically and the backend sets a new access cookie.
        await api.post('/users/token/refresh/');
        isRefreshing = false;
        onRefreshed();
        return api(originalRequest);
      } catch (refreshError) {
        isRefreshing = false;
        refreshSubscribers = [];
        // Refresh failed — clear any lingering cookies via the logout endpoint
        try { await api.post('/users/logout/'); } catch (_) {}
        // Redirect to login
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  },
);

// ── Helper ─────────────────────────────────────────────────────────────────
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// ── CSRF primer ─────────────────────────────────────────────────────────────
// On module load, hit the CSRF endpoint so Django sets the csrftoken cookie.
// This ensures the cookie exists before the first POST (e.g. login) fires.
api.get('/csrf/').catch(() => {
  // Silently ignore — not critical, Django sets the cookie on the next
  // request anyway.  This just pre-warms it.
});

export default api;
