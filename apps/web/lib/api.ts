export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  'https://quantos-api.onrender.com';

const TOKEN_KEY = 'prismflow_token';
const USER_KEY = 'prismflow_user';
const REFRESH_KEY = 'quantos_refresh_token';

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  onboarding_completed?: boolean;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function getToken(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem('token') || '';
}

export function getUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  } catch {
    return null;
  }
}

export function saveAuth(data: { token?: string; access_token?: string; refresh_token?: string; user?: AuthUser }) {
  if (typeof window === 'undefined') return;
  const access = data?.access_token || data?.token;
  if (access) {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem('token', access);
  }
  if (data?.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
  if (data?.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user));
}

export function clearAuth() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem('token');
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem('prismflow_last_job');
}

export function logout() {
  const token = getToken();
  clearAuth();
  if (token) {
    fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    }).catch(() => {});
  }
  if (typeof window !== 'undefined') {
    window.location.href = '/login';
  }
}

function formatDetailItem(item: unknown): string {
  if (item == null) return '';
  if (typeof item === 'string') return item;
  if (typeof item === 'object') {
    const obj = item as Record<string, unknown>;
    if (typeof obj.msg === 'string') return obj.msg;
    if (typeof obj.message === 'string') return obj.message;
    if (typeof obj.detail === 'string') return obj.detail;
    try {
      return JSON.stringify(item);
    } catch {
      return String(item);
    }
  }
  return String(item);
}

function normalizeError(data: unknown, status: number): string {
  if (!data) return `Request failed (${status})`;
  if (typeof data === 'string') return data;
  if (typeof data !== 'object') return `Request failed (${status})`;

  const body = data as Record<string, unknown>;
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) {
    const parts = body.detail.map(formatDetailItem).filter(Boolean);
    if (parts.length) return parts.join('; ');
  }
  if (body.detail && typeof body.detail === 'object') {
    const detail = formatDetailItem(body.detail);
    if (detail) return detail;
  }
  if (typeof body.error === 'string') return body.error;
  if (typeof body.message === 'string') return body.message;
  try {
    return JSON.stringify(data);
  } catch {
    return `Request failed (${status})`;
  }
}

export function formatApiError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  if (err && typeof err === 'object') {
    const maybe = err as { message?: unknown; detail?: unknown };
    if (typeof maybe.message === 'string') return maybe.message;
    if (typeof maybe.detail === 'string') return maybe.detail;
    if (Array.isArray(maybe.detail)) {
      return maybe.detail.map(formatDetailItem).filter(Boolean).join('; ');
    }
  }
  return 'An unexpected error occurred';
}

let redirectingToLogin = false;

function handleUnauthorized() {
  if (typeof window === 'undefined' || redirectingToLogin) return;
  const path = window.location.pathname;
  if (path === '/login' || path === '/') return;
  redirectingToLogin = true;
  clearAuth();
  const expired = path !== '/login' ? '?expired=1' : '';
  window.location.href = `/login${expired}`;
}

export async function fetchMe(): Promise<AuthUser> {
  const user = await api('/auth/me') as AuthUser;
  saveAuth({ user });
  return user;
}

export async function restoreSession(): Promise<AuthUser | null> {
  if (!getToken()) return null;
  try {
    return await fetchMe();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      const refresh = typeof window !== 'undefined' ? localStorage.getItem(REFRESH_KEY) : '';
      if (refresh) {
        try {
          const data = await api('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: refresh }) });
          saveAuth(data);
          return await fetchMe();
        } catch { /* fall through */ }
      }
      clearAuth();
      return null;
    }
    throw err;
  }
}

export async function api(path: string, options: RequestInit = {}) {
  const token = getToken();
  const incomingHeaders = (options.headers as Record<string, string>) || {};
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...incomingHeaders };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(
      `Cannot reach QuantOS API at ${API_BASE}. Please start the backend and refresh this page.`,
      0
    );
  }

  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    const message = normalizeError(data, res.status);
    if (res.status === 401 && !path.startsWith('/auth/login') && !path.startsWith('/auth/register')) {
      handleUnauthorized();
    }
    throw new ApiError(message, res.status);
  }

  return data;
}
