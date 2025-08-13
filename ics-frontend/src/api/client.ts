// src/api/client.ts
import axios, { AxiosHeaders } from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

declare global {
  interface Window {
    RUNTIME_CONFIG?: { API_BASE_URL?: string; API_KEY?: string };
  }
}
const LS_API_BASE = 'apiBase';
const LS_API_KEY = 'apiKey';

function fromRuntime(key: 'API_BASE_URL' | 'API_KEY'): string {
  return (window.RUNTIME_CONFIG?.[key] ?? '').trim();
}

export function getApiBase(): string {
  const ls = (localStorage.getItem(LS_API_BASE) ?? '').trim();
  if (ls) return ls.replace(/\/+$/, '');

  const runtime = fromRuntime('API_BASE_URL');
  if (runtime) return runtime.replace(/\/+$/, '');

  const env = (import.meta.env.VITE_API_BASE_URL ?? '').trim();
  return env.replace(/\/+$/, '');
}

export function getApiKey(): string {
  const lsRaw = localStorage.getItem(LS_API_KEY);
  const ls = (lsRaw ?? '').trim();
  if (ls && ls.toLowerCase() !== 'null' && ls.toLowerCase() !== 'undefined') return ls;

  const runtime = fromRuntime('API_KEY');
  if (runtime) return runtime;

  return (import.meta.env.VITE_API_KEY ?? '').trim();
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
    // eslint-disable-next-line no-console
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
      window.location.assign('/settings');
    }
    return Promise.reject(err);
  }
);
