import {
  CrawlConfig,
  DataFileInfo,
  DataPreview,
  LogEntry,
  RuntimeState,
  TaskRecord,
  TemplateRecord,
} from './types';

const TOKEN_KEY = 'mediacrawler_webui_token';

function authToken() {
  const token = window.localStorage.getItem(TOKEN_KEY);
  return token?.trim() || '';
}

function buildHeaders(initHeaders?: HeadersInit) {
  const headers = new Headers(initHeaders);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const token = authToken();
  if (token) {
    headers.set('X-WebUI-Token', token);
  }
  return headers;
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: buildHeaders(init?.headers),
  });

  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = body.detail || body.message || message;
    } catch {
      // Keep status text.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

function encodePath(path: string) {
  return path.split('/').map(encodeURIComponent).join('/');
}

export function setAuthToken(token: string) {
  const cleaned = token.trim();
  if (cleaned) {
    window.localStorage.setItem(TOKEN_KEY, cleaned);
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}

export function getWsUrl(path: string) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
}

export const api = {
  health: () => jsonRequest<{ status: string }>('/api/health'),
  status: () => jsonRequest<RuntimeState>('/api/crawler/status'),
  start: (config: CrawlConfig) =>
    jsonRequest<{ status: string; message: string; task: TaskRecord }>('/api/crawler/start', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
  stop: (taskId?: string | null) =>
    jsonRequest<{ status: string; message: string }>(
      `/api/crawler/stop${taskId ? `?task_id=${encodeURIComponent(taskId)}` : ''}`,
      { method: 'POST' },
    ),
  tasks: () => jsonRequest<TaskRecord[]>('/api/crawler/tasks?limit=100'),
  taskLogs: (taskId: string) =>
    jsonRequest<{ logs: LogEntry[] }>(`/api/crawler/tasks/${encodeURIComponent(taskId)}/logs?limit=500`),
  templates: () => jsonRequest<TemplateRecord[]>('/api/templates'),
  files: () => jsonRequest<{ files: DataFileInfo[] }>('/api/data/files'),
  preview: (path: string) =>
    jsonRequest<DataPreview>(`/api/data/files/${encodePath(path)}?preview=true&limit=100`),
  downloadUrl: (path: string) => `/api/data/download/${encodePath(path)}`,
};
