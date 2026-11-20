import axios from 'axios';

const BASE_URL = `${import.meta.env.VITE_API_URL || ''}/api/v1`;

/** Single Axios instance for the whole app. Adds the JWT and refreshes it automatically on 401. */
export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

const ACCESS = 'arb_access';
const REFRESH = 'arb_refresh';

function safeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokenStore = {
  getAccess: () => safeGet(ACCESS),
  getRefresh: () => safeGet(REFRESH),
  set: ({ access, refresh }) => {
    try {
      if (access) localStorage.setItem(ACCESS, access);
      if (refresh) localStorage.setItem(REFRESH, refresh);
    } catch {
      /* storage unavailable */
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(ACCESS);
      localStorage.removeItem(REFRESH);
    } catch {
      /* storage unavailable */
    }
  },
};

/** AuthContext listens for this to drop the user back to the login page. */
export const SESSION_EXPIRED_EVENT = 'arb:session-expired';

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  // File uploads: let the browser set multipart/form-data with the boundary
  if (typeof FormData !== 'undefined' && config.data instanceof FormData)
    config.headers.setContentType?.(null, true) ?? delete config.headers['Content-Type'];
  return config;
});

// ---- Automatic token refresh (one refresh at a time; other requests wait in a queue) ----
let refreshPromise = null;

function refreshTokens() {
  if (!refreshPromise) {
    const refresh = tokenStore.getRefresh();
    refreshPromise = (
      refresh
        ? axios.post(`${BASE_URL}/auth/refresh/`, { refresh })
        : Promise.reject(new Error('No refresh token'))
    )
      .then(({ data }) => {
        tokenStore.set(data);
        return data.access;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

const NO_REFRESH_URLS = [
  '/auth/login/',
  '/auth/refresh/',
  '/auth/forgot-password/',
  '/auth/reset-password/',
];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const skip =
      !original || original._retry || NO_REFRESH_URLS.some((u) => original.url?.includes(u));
    if (status !== 401 || skip) return Promise.reject(error);

    original._retry = true;
    try {
      const access = await refreshTokens();
      original.headers.Authorization = `Bearer ${access}`;
      return api(original);
    } catch {
      tokenStore.clear();
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      return Promise.reject(error);
    }
  },
);

/** Turns the backend error format {detail, errors} into one readable message. */
export function getErrorMessage(error) {
  if (!error?.response) return 'Cannot reach the server. Check your connection.';
  const data = error.response.data || {};
  if (error.response.status === 429) {
    // account lockout explains itself; plain rate limits get a generic message
    if (data.detail && !/^Request was throttled/.test(data.detail)) return data.detail;
    return 'Too many attempts. Please wait a minute and try again.';
  }
  if (data.errors && Object.keys(data.errors).length) {
    const [field, messages] = Object.entries(data.errors)[0];
    const msg = Array.isArray(messages) ? messages[0] : messages;
    if (field === 'non_field_errors' || field === 'detail') return String(msg);
    return `${field.replace(/_/g, ' ')}: ${msg}`;
  }
  return data.detail || `Request failed (${error.response.status})`;
}

/** Copies backend field errors onto a react-hook-form instance. Returns true if any were set. */
export function applyFieldErrors(error, setError) {
  const errors = error?.response?.data?.errors;
  if (!errors || typeof errors !== 'object') return false;
  let applied = false;
  Object.entries(errors).forEach(([field, messages]) => {
    // non-field errors have no input to show under — let the caller toast them
    if (field === 'non_field_errors' || field === 'detail') return;
    const message = Array.isArray(messages) ? messages[0] : String(messages);
    setError(field, { type: 'server', message });
    applied = true;
  });
  return applied;
}
