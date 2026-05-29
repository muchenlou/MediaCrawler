export type PlatformValue = 'xhs' | 'dy' | 'ks' | 'bili' | 'wb' | 'tieba' | 'zhihu';
export type LoginType = 'qrcode' | 'phone' | 'cookie';
export type CrawlerType = 'search' | 'detail' | 'creator';
export type SaveOption = 'jsonl' | 'json' | 'csv' | 'excel' | 'sqlite' | 'db' | 'mongodb';
export type SearchSortType = 'general' | 'popularity_descending' | 'time_descending';
export type RuntimeStatus = 'idle' | 'running' | 'stopping' | 'error';
export type TaskStatus = 'queued' | 'running' | 'stopping' | 'completed' | 'failed' | 'stopped';

export interface CrawlConfig {
  task_name: string;
  tags: string[];
  source_template_id: string;
  platform: PlatformValue;
  login_type: LoginType;
  crawler_type: CrawlerType;
  keywords: string;
  specified_ids: string;
  creator_ids: string;
  sort_type: SearchSortType;
  max_notes_count: number;
  start_page: number;
  enable_comments: boolean;
  enable_sub_comments: boolean;
  save_option: SaveOption;
  cookies: string;
  headless: boolean;
  cdp_connect_existing: boolean;
  cdp_debug_port: number;
}

export interface RuntimeState {
  status: RuntimeStatus;
  active_task_id: string | null;
  queued_count: number;
  platform: string | null;
  crawler_type: string | null;
  started_at: string | null;
  error_message: string | null;
}

export interface LogEntry {
  id: number;
  task_id: string | null;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success' | 'debug';
  message: string;
}

export interface TaskRecord {
  id: string;
  name: string;
  status: TaskStatus;
  platform: PlatformValue;
  crawler_type: CrawlerType;
  save_option: SaveOption;
  login_type: LoginType;
  target: string;
  tags: string[];
  source_template_id: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  command: string[];
  result_files: string[];
  logs_count: number;
  error_message: string | null;
  config: CrawlConfig;
}

export interface TemplateRecord {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  config: CrawlConfig;
  created_at: string;
  updated_at: string;
}

export interface DataFileInfo {
  name: string;
  path: string;
  size: number;
  modified_at: number;
  record_count: number | null;
  type: string;
}

export interface DataPreview {
  data: Record<string, unknown>[] | Record<string, unknown>;
  total: number;
  columns?: string[];
}
