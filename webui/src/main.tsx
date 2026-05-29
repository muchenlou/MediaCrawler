import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Database,
  Download,
  FileText,
  KeyRound,
  Layers3,
  Loader2,
  Octagon,
  Play,
  RefreshCcw,
  Search,
  Settings2,
  SquareTerminal,
  Table2,
} from 'lucide-react';
import { api, getWsUrl, setAuthToken } from './api';
import {
  CrawlConfig,
  DataFileInfo,
  DataPreview,
  LogEntry,
  RuntimeState,
  TaskRecord,
  TemplateRecord,
} from './types';
import './styles.css';

type Notice = {
  kind: 'success' | 'error';
  message: string;
};

const platformOptions = [
  ['xhs', '小红书'],
  ['dy', '抖音'],
  ['ks', '快手'],
  ['bili', 'B站'],
  ['wb', '微博'],
  ['tieba', '贴吧'],
  ['zhihu', '知乎'],
] as const;

const defaultConfig: CrawlConfig = {
  task_name: '',
  tags: [],
  source_template_id: '',
  platform: 'xhs',
  login_type: 'qrcode',
  crawler_type: 'search',
  keywords: '',
  specified_ids: '',
  creator_ids: '',
  sort_type: 'time_descending',
  max_notes_count: 20,
  start_page: 1,
  enable_comments: true,
  enable_sub_comments: false,
  save_option: 'jsonl',
  cookies: '',
  headless: false,
  cdp_connect_existing: false,
  cdp_debug_port: 9222,
};

function App() {
  const [config, setConfig] = useState<CrawlConfig>(defaultConfig);
  const [tagsText, setTagsText] = useState('');
  const [runtime, setRuntime] = useState<RuntimeState | null>(null);
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [files, setFiles] = useState<DataFileInfo[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [preview, setPreview] = useState<DataPreview | null>(null);
  const [previewQuery, setPreviewQuery] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [loading, setLoading] = useState(false);
  const selectedTaskRef = useRef<string | null>(null);
  const taskStatusRef = useRef<Record<string, TaskRecord['status']>>({});

  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) || null,
    [selectedTaskId, tasks],
  );

  const scopedFiles = useMemo(() => {
    if (!selectedTask?.result_files.length) return files;
    return files.filter((file) => selectedTask.result_files.includes(file.path));
  }, [files, selectedTask]);

  const targetField = config.crawler_type === 'detail'
    ? ['specified_ids', '内容 ID / URL', '多个 ID 或 URL 用英文逗号分隔'] as const
    : config.crawler_type === 'creator'
      ? ['creator_ids', '创作者 ID / 主页 URL', '多个主页 URL 或 ID 用英文逗号分隔'] as const
      : ['keywords', '搜索关键词', '多个关键词用英文逗号分隔'] as const;

  const refresh = useCallback(async () => {
    try {
      const [statusRes, templateRes, taskRes, fileRes] = await Promise.all([
        api.status(),
        api.templates(),
        api.tasks(),
        api.files(),
      ]);
      setRuntime(statusRes);
      setTemplates(templateRes);
      setTasks(taskRes);
      setFiles(fileRes.files);
      setSelectedTaskId((current) => current || statusRes.active_task_id || taskRes[0]?.id || null);
    } catch (error) {
      setNotice({ kind: 'error', message: error instanceof Error ? error.message : '刷新失败' });
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 2500);
    return () => window.clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    selectedTaskRef.current = selectedTaskId;
  }, [selectedTaskId]);

  useEffect(() => {
    const previous = taskStatusRef.current;
    const finishedTask = tasks.find((task) => (
      task.status === 'completed' && ['queued', 'running', 'stopping'].includes(previous[task.id] || '')
    ));

    if (finishedTask) {
      setSelectedTaskId(finishedTask.id);
      setNotice({
        kind: 'success',
        message: `采集已完成：${finishedTask.name || finishedTask.id}，生成 ${finishedTask.result_files.length} 个结果文件。`,
      });
    }

    taskStatusRef.current = Object.fromEntries(tasks.map((task) => [task.id, task.status]));
  }, [tasks]);

  useEffect(() => {
    if (!selectedTaskId) {
      setLogs([]);
      return;
    }

    api.taskLogs(selectedTaskId)
      .then((res) => setLogs(res.logs))
      .catch((error) => setNotice({ kind: 'error', message: error instanceof Error ? error.message : '日志加载失败' }));
  }, [selectedTaskId]);

  useEffect(() => {
    setSelectedFile((current) => {
      if (current && scopedFiles.some((file) => file.path === current)) return current;
      return scopedFiles[0]?.path || null;
    });
  }, [scopedFiles]);

  useEffect(() => {
    if (!selectedFile) {
      setPreview(null);
      return;
    }
    api.preview(selectedFile)
      .then(setPreview)
      .catch((error) => {
        setPreview(null);
        setNotice({ kind: 'error', message: error instanceof Error ? error.message : '预览加载失败' });
      });
  }, [selectedFile]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnect: number | undefined;

    const connect = () => {
      socket = new WebSocket(getWsUrl('/api/ws/logs'));
      socket.onmessage = (event) => {
        if (event.data === 'ping') {
          socket?.send('pong');
          return;
        }
        try {
          const entry = JSON.parse(event.data) as LogEntry;
          if (entry.task_id && entry.task_id !== selectedTaskRef.current) return;
          setLogs((current) => {
            if (current.some((item) => item.id === entry.id && item.task_id === entry.task_id)) return current;
            return [...current, entry].slice(-500);
          });
        } catch {
          // keepalive frame
        }
      };
      socket.onclose = () => {
        reconnect = window.setTimeout(connect, 2000);
      };
    };

    connect();
    return () => {
      if (reconnect) window.clearTimeout(reconnect);
      socket?.close();
    };
  }, []);

  function applyTemplate(template: TemplateRecord) {
    setConfig({ ...template.config, source_template_id: template.id });
    setTagsText(template.config.tags.join(','));
  }

  async function startTask(nextConfig = config) {
    setLoading(true);
    setNotice(null);
    try {
      const res = await api.start({
        ...nextConfig,
        tags: tagsText.split(',').map((tag) => tag.trim()).filter(Boolean),
      });
      setSelectedTaskId(res.task.id);
      await refresh();
    } catch (error) {
      setNotice({ kind: 'error', message: error instanceof Error ? error.message : '启动失败' });
    } finally {
      setLoading(false);
    }
  }

  async function stopTask() {
    setLoading(true);
    try {
      await api.stop(selectedTaskId);
      await refresh();
    } catch (error) {
      setNotice({ kind: 'error', message: error instanceof Error ? error.message : '停止失败' });
    } finally {
      setLoading(false);
    }
  }

  const rows = normalizeRows(preview);
  const columns = getColumns(preview, rows);
  const filteredRows = filterRows(rows, columns, previewQuery);
  const isRunning = runtime?.status === 'running' || runtime?.status === 'stopping';

  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="brand-mark">MC</div>
        <button className="rail-button active" title="控制台"><Database size={18} /></button>
        <button className="rail-button" title="模板"><Layers3 size={18} /></button>
        <button className="rail-button" title="结果"><Table2 size={18} /></button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>MediaCrawler 控制台</h1>
            <p>任务、模板、日志和结果集中管理</p>
          </div>
          <div className="top-actions">
            <RuntimeBadge runtime={runtime} />
            <button className="icon-button" onClick={refresh} title="刷新"><RefreshCcw size={16} /></button>
          </div>
        </header>

        {notice && (
          <div className={`notice ${notice.kind}`}>
            {notice.kind === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            <span>{notice.message}</span>
            <button onClick={() => setNotice(null)}>关闭</button>
          </div>
        )}

        <section className="grid-main">
          <Panel title="采集任务" icon={<Settings2 size={18} />} className="config-panel">
            <div className="form-grid">
              <Field label="任务名称">
                <input value={config.task_name} onChange={(e) => setConfig({ ...config, task_name: e.target.value })} placeholder="例如：竞品内容监控" />
              </Field>
              <Field label="平台">
                <select value={config.platform} onChange={(e) => setConfig({ ...config, platform: e.target.value as CrawlConfig['platform'] })}>
                  {platformOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </Field>
              <Field label="采集类型">
                <select value={config.crawler_type} onChange={(e) => setConfig({ ...config, crawler_type: e.target.value as CrawlConfig['crawler_type'] })}>
                  <option value="search">搜索</option>
                  <option value="detail">详情</option>
                  <option value="creator">创作者</option>
                </select>
              </Field>
              <Field label="登录方式">
                <select value={config.login_type} onChange={(e) => setConfig({ ...config, login_type: e.target.value as CrawlConfig['login_type'] })}>
                  <option value="qrcode">二维码</option>
                  <option value="cookie">Cookie</option>
                  <option value="phone">手机号</option>
                </select>
              </Field>
            </div>

            <Field label={targetField[1]}>
              <textarea
                value={String(config[targetField[0]])}
                onChange={(e) => setConfig({ ...config, [targetField[0]]: e.target.value })}
                placeholder={targetField[2]}
                rows={4}
              />
            </Field>

            {config.login_type === 'cookie' && (
              <Field label="Cookie">
                <textarea value={config.cookies} onChange={(e) => setConfig({ ...config, cookies: e.target.value })} rows={3} />
              </Field>
            )}

            {config.platform === 'xhs' && config.crawler_type === 'search' && (
              <Field label="小红书排序">
                <select value={config.sort_type} onChange={(e) => setConfig({ ...config, sort_type: e.target.value as CrawlConfig['sort_type'] })}>
                  <option value="time_descending">最新</option>
                  <option value="popularity_descending">最热</option>
                  <option value="general">综合</option>
                </select>
              </Field>
            )}

            <div className="form-grid compact">
              <Field label="保存格式">
                <select value={config.save_option} onChange={(e) => setConfig({ ...config, save_option: e.target.value as CrawlConfig['save_option'] })}>
                  <option value="jsonl">JSONL</option>
                  <option value="excel">Excel</option>
                  <option value="csv">CSV</option>
                  <option value="json">JSON</option>
                  <option value="sqlite">SQLite</option>
                </select>
              </Field>
              <Field label="起始页">
                <input type="number" min={1} value={config.start_page} onChange={(e) => setConfig({ ...config, start_page: Number(e.target.value) || 1 })} />
              </Field>
              <Field label="采集数量">
                <input type="number" min={1} step={1} value={config.max_notes_count} onChange={(e) => setConfig({ ...config, max_notes_count: Number(e.target.value) || 20 })} />
              </Field>
              <Field label="标签">
                <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} placeholder="舆情,竞品" />
              </Field>
            </div>

            <div className="switch-row">
              <Switch checked={config.enable_comments} onChange={(checked) => setConfig({ ...config, enable_comments: checked })} label="一级评论" />
              <Switch checked={config.enable_sub_comments} onChange={(checked) => setConfig({ ...config, enable_sub_comments: checked })} label="二级评论" />
              <Switch checked={config.headless} onChange={(checked) => setConfig({ ...config, headless: checked })} label="无头模式" />
              <Switch checked={config.cdp_connect_existing} onChange={(checked) => setConfig({ ...config, cdp_connect_existing: checked })} label="连接已有浏览器" />
            </div>

            <div className="button-row">
              <button className="primary" onClick={() => startTask()} disabled={loading || isRunning}>
                {loading ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
                开始采集
              </button>
              <button className="danger" onClick={stopTask} disabled={!isRunning || loading}>
                <Octagon size={16} />
                停止
              </button>
            </div>
          </Panel>

          <Panel title="采集模板" icon={<Layers3 size={18} />}>
            <div className="template-list">
              {templates.map((template) => (
                <div className="template-item" key={template.id}>
                  <div>
                    <strong>{template.name}</strong>
                    <p>{template.description}</p>
                    <div className="tag-row">
                      <span>{template.category}</span>
                      {template.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
                    </div>
                  </div>
                  <div className="template-actions">
                    <button onClick={() => applyTemplate(template)}>套用</button>
                    <button onClick={() => startTask({ ...template.config, source_template_id: template.id })}>执行</button>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="任务队列" icon={<FileText size={18} />}>
            <div className="task-list">
              {tasks.length === 0 && <Empty text="暂无任务" />}
              {tasks.map((task) => (
                <button className={`task-row ${task.id === selectedTaskId ? 'selected' : ''}`} key={task.id} onClick={() => setSelectedTaskId(task.id)}>
                  <span className={`dot ${task.status}`} />
                  <span>
                    <strong>{task.name || `${task.platform.toUpperCase()} ${task.crawler_type}`}</strong>
                    <small>{formatTime(task.created_at)} · {task.logs_count} 行日志 · {task.result_files.length} 文件</small>
                  </span>
                  <em>{statusLabel(task.status)}</em>
                </button>
              ))}
            </div>
          </Panel>
        </section>

        <section className="lower-grid">
          <Panel title="实时日志" icon={<SquareTerminal size={18} />}>
            <div className="log-view">
              {logs.length === 0 && <Empty text="等待任务日志" />}
              {logs.map((log) => (
                <div className={`log-line ${log.level}`} key={`${log.task_id}-${log.id}`}>
                  <span>[{log.timestamp}]</span>
                  <code>{log.message}</code>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="数据结果" icon={<Table2 size={18} />}>
            <div className="result-layout">
              <div className="file-list">
                {scopedFiles.length === 0 && <Empty text="暂无结果文件" />}
                {scopedFiles.map((file) => (
                  <button key={file.path} className={file.path === selectedFile ? 'selected' : ''} onClick={() => setSelectedFile(file.path)}>
                    <span>{file.name}</span>
                    <small>{file.type.toUpperCase()} · {formatBytes(file.size)}</small>
                  </button>
                ))}
              </div>
              <div className="preview-area">
                <div className="preview-toolbar">
                  <label>
                    <Search size={15} />
                    <input value={previewQuery} onChange={(e) => setPreviewQuery(e.target.value)} placeholder="筛选预览内容" />
                  </label>
                  {selectedFile && <a href={api.downloadUrl(selectedFile)}><Download size={15} />下载</a>}
                </div>
                <div className="table-wrap">
                  {!preview && <Empty text="选择文件后预览" />}
                  {preview && (
                    <table>
                      <thead>
                        <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
                      </thead>
                      <tbody>
                        {filteredRows.map((row, index) => (
                          <tr key={index}>{columns.map((column) => <td key={column}>{stringify(row[column])}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          </Panel>
        </section>

        <section className="token-strip">
          <KeyRound size={15} />
          <span>如果后端设置了 WEBUI_AUTH_TOKEN，在这里输入令牌后再刷新接口。</span>
          <input type="password" placeholder="WebUI Token" onBlur={(event) => setAuthToken(event.currentTarget.value)} />
        </section>
      </main>
    </div>
  );
}

function Panel({ title, icon, children, className = '' }: { title: string; icon: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <header>
        <span>{icon}</span>
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function Switch({ checked, onChange, label }: { checked: boolean; onChange: (checked: boolean) => void; label: string }) {
  return (
    <label className="switch">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span />
      {label}
    </label>
  );
}

function RuntimeBadge({ runtime }: { runtime: RuntimeState | null }) {
  const running = runtime?.status === 'running';
  return (
    <div className={`runtime-badge ${runtime?.status || 'idle'}`}>
      {running ? <Loader2 className="spin" size={15} /> : runtime?.status === 'idle' ? <CheckCircle2 size={15} /> : <Circle size={15} />}
      <span>{runtime ? statusLabel(runtime.status) : '连接中'}</span>
      {runtime?.queued_count ? <small>{runtime.queued_count} 排队</small> : null}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}

function normalizeRows(preview: DataPreview | null) {
  if (!preview) return [];
  return Array.isArray(preview.data) ? preview.data : [preview.data];
}

function getColumns(preview: DataPreview | null, rows: Record<string, unknown>[]) {
  if (preview?.columns?.length) return preview.columns.slice(0, 14);
  const keys = new Set<string>();
  rows.slice(0, 20).forEach((row) => Object.keys(row).forEach((key) => keys.add(key)));
  return Array.from(keys).slice(0, 14);
}

function filterRows(rows: Record<string, unknown>[], columns: string[], query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) => columns.some((column) => stringify(row[column]).toLowerCase().includes(needle)));
}

function stringify(value: unknown) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    idle: '空闲',
    running: '运行中',
    stopping: '停止中',
    error: '异常',
    queued: '排队中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止',
  };
  return labels[status] || status;
}

function formatTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

createRoot(document.getElementById('root')!).render(<App />);
