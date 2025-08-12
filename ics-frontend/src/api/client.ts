// src/api/client.ts
import axios, { AxiosHeaders } from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

const LS_API_BASE = 'apiBase';
const LS_API_KEY = 'apiKey';

declare global {
  interface Window {
    RUNTIME_CONFIG?: {
      API_BASE_URL?: string;
      API_KEY?: string;
    };
  }
}

function fromRuntime(k: keyof NonNullable<Window['RUNTIME_CONFIG']>): string {
  try {
    return (window.RUNTIME_CONFIG?.[k] ?? '').toString();
  } catch {
    return '';
  }
}

export function getApiBase(): string {
  // Priority: localStorage → runtime-config.js → build-time VITE_ → ''
  const ls = (window.localStorage.getItem(LS_API_BASE) ?? '').trim();
  const runtime = fromRuntime('API_BASE_URL').trim();
  const env = (import.meta.env.VITE_API_BASE_URL ?? '').trim();

  const candidate = ls || runtime || env || '';
  return candidate.replace(/\/+$/, ''); // strip trailing slashes
}

export function getApiKey(): string {
  // Priority: localStorage (if not blank/null/undefined) → runtime-config.js → build-time VITE_
  const lsRaw = window.localStorage.getItem(LS_API_KEY);
  const cleaned = (lsRaw ?? '').trim().toLowerCase();
  const useLs = cleaned.length > 0 && cleaned !== 'null' && cleaned !== 'undefined';

  const runtime = fromRuntime('API_KEY').trim();
  const env = (import.meta.env.VITE_API_KEY ?? '').trim();

  return (useLs ? (lsRaw as string) : (runtime || env)).trim();
}

export const api = axios.create({
  baseURL: getApiBase(),
  timeout: 20000,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // Refresh baseURL each request in case user changed Settings or runtime-config loaded late
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

// Global 401/403 handling → redirect to Settings
api.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    const status = err.response?.status;
    if (status === 401 || status === 403) {
      try {
        alert('Session invalid. Please enter your API key again.');
      } catch {}
      window.location.href = '/settings';
    }
    return Promise.reject(err);
  }
);
