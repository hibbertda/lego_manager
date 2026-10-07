import axios from 'axios';

// All requests are same-origin in both dev (via vite.config.ts proxy) and
// prod (Flask serves the built SPA), so the session cookie travels
// automatically — no token-based auth needed. `withCredentials` is kept
// explicit anyway as defense-in-depth against any future cross-origin setup.
export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

// Mutating requests need the CSRF token Flask-WTF expects in the
// `X-CSRFToken` header (see GET /api/session's csrf_token field). We cache
// the latest token here whenever AuthContext refreshes the session, and
// attach it to every state-changing request via this interceptor so
// individual page components never have to think about it.
let csrfToken = '';

export function setCsrfToken(token: string) {
  csrfToken = token;
}

api.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase();
  if (method !== 'get' && csrfToken) {
    config.headers = config.headers || {};
    config.headers['X-CSRFToken'] = csrfToken;
  }
  return config;
});

export interface ApiErrorBody {
  error?: string;
}

export function extractErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as ApiErrorBody | undefined;
    if (body?.error) return body.error;
  }
  return fallback;
}
