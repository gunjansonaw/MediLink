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
    // Read the CSRF token from the cookie Django sets (csrftoken). When the API
    // is on another origin the cookie is unreadable, so fall back to the token
    // returned by /csrf/.
    const csrfToken = getCookie('csrftoken') || csrfTokenFromApi;
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

function settleSubscribers(error) {
  // Resolve (replay) or reject every request queued during the refresh.
  // Previously failed refreshes left these promises pending forever.
  refreshSubscribers.forEach(({ resolve, reject }) => (error ? reject(error) : resolve()));
  refreshSubscribers = [];
}

const PUBLIC_PATHS = ['/login', '/register'];
const NO_RETRY_URLS = ['/users/token/refresh/', '/users/login/', '/users/logout/'];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      originalRequest &&
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !NO_RETRY_URLS.some((u) => originalRequest.url?.includes(u))
    ) {
      if (isRefreshing) {
        // Queue requests while a refresh is in-flight
        return new Promise((resolve, reject) => {
          refreshSubscribers.push({
            resolve: () => resolve(api(originalRequest)),
            reject,
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
        settleSubscribers(null);
        return api(originalRequest);
      } catch (refreshError) {
        isRefreshing = false;
        settleSubscribers(refreshError);
        // Refresh failed — clear any lingering cookies via the logout endpoint
        try { await api.post('/users/logout/'); } catch (_) {}
        // Redirect to login — but never from a public page, which previously
        // caused an infinite reload loop on /login when logged out.
        if (!PUBLIC_PATHS.includes(window.location.pathname)) {
          window.location.href = '/login';
        }
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
let csrfTokenFromApi = null;
export const csrfReady = api.get('/csrf/')
  .then((resp) => { csrfTokenFromApi = resp.data?.csrfToken || null; })
  .catch(() => {
    // Not critical — Django sets the cookie on the next request anyway.
  });

export const API_URL_BASE = API_URL;

export default api;
