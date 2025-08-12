import axios, { AxiosHeaders } from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

declare global {
  interface Window {
    __ENV__?: { API_BASE_URL?: string; API_KEY?: string };
  }
}

const LS_API_BASE = 'apiBase';
const LS_API_KEY = 'apiKey';

function getRuntime(key: 'API_BASE_URL' | 'API_KEY'): string {
  return (window.__ENV__?.[key] ?? '').trim();
}

export function getApiBase(): string {
  const ls = window.localStorage.getItem(LS_API_BASE) || '';
  const env =
    import.meta.env.VITE_API_BASE_URL ||
    getRuntime('API_BASE_URL') ||
    '';
  return (ls || env).replace(/\/+$/, '');
}

export function getApiKey(): string {
  const ls = (window.localStorage.getItem(LS_API_KEY) ?? '').trim();
  const baked = (import.meta.env.VITE_API_KEY ?? '').trim();
  const runtime = getRuntime('API_KEY');
  // Preference: localStorage (user override) → runtime (injected) → baked (build-time)
  return (ls || runtime || baked).trim();
}

export const api = axios.create({
  baseURL: getApiBase(),
  timeout: 20000,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  config.baseURL = getApiBase();

  const headers =
    config.headers instanceof AxiosHeaders
      ? config.headers
      : new AxiosHeaders(config.headers);

  const key = getApiKey();
  if (key) headers.set('x-api-key', key);

  const method = (config.method || 'get').toLowerCase();
  if (method !== 'get' && method !== 'head') {
    headers.set('Content-Type', 'application/json');
  } else {
    headers.delete('Content-Type');
  }

  config.headers = headers;

  if (import.meta.env.DEV) {
    const url = `${config.baseURL ?? ''}${config.url ?? ''}`;
    console.debug('[api]', method.toUpperCase(), url, { params: config.params });
  }

  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    const status = err.response?.status;
    if (status === 401 || status === 403) {
      try { alert('Session invalid. Please enter your API key again.'); } catch {}
      window.location.href = '/settings';
    }
    return Promise.reject(err);
  }
);
