# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/services/crawler_manager.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import json
import os
import signal
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..schemas import CrawlerStartRequest, LogEntry, TaskRecord


class CrawlerManager:
    """Crawler process and lightweight task queue manager."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.process: Optional[subprocess.Popen] = None
        self.status = "idle"
        self.started_at: Optional[datetime] = None
        self.current_config: Optional[CrawlerStartRequest] = None
        self.active_task_id: Optional[str] = None
        self._log_id = 0
        self._logs: List[LogEntry] = []
        self._task_logs: Dict[str, List[LogEntry]] = {}
        self._read_task: Optional[asyncio.Task] = None
        self._project_root = Path(__file__).parent.parent.parent
        self._data_dir = self._project_root / "data"
        self._tasks_file = self._data_dir / "webui_tasks.json"
        self._log_queue: Optional[asyncio.Queue] = None
        self._tasks: Dict[str, TaskRecord] = {}
        self._task_order: List[str] = []
        self._pending_task_ids: List[str] = []
        self._task_configs: Dict[str, CrawlerStartRequest] = {}
        self._task_file_snapshots: Dict[str, set[str]] = {}
        self._load_tasks()

    @property
    def logs(self) -> List[LogEntry]:
        if self.active_task_id:
            return self._task_logs.get(self.active_task_id, [])
        if self._task_order:
            return self._task_logs.get(self._task_order[-1], [])
        return self._logs

    @property
    def tasks(self) -> List[TaskRecord]:
        return [self._tasks[task_id] for task_id in reversed(self._task_order) if task_id in self._tasks]

    def get_log_queue(self) -> asyncio.Queue:
        """Get or create log queue."""
        if self._log_queue is None:
            self._log_queue = asyncio.Queue()
        return self._log_queue

    async def start(self, config: CrawlerStartRequest) -> TaskRecord:
        """Create a task and start it immediately or enqueue it."""
        async with self._lock:
            task = self._create_task(config)
            self._tasks[task.id] = task
            self._task_order.append(task.id)
            self._task_logs[task.id] = []
            self._task_configs[task.id] = config

            if self.process and self.process.poll() is None:
                self._pending_task_ids.append(task.id)
                await self._push_log(self._create_log_entry("Task queued; waiting for current crawler to finish.", "info", task.id))
                self._persist_tasks()
                return task

            await self._launch_task(task.id)
            return self._tasks[task.id]

    async def stop(self, task_id: Optional[str] = None) -> bool:
        """Stop the active task, or cancel a queued task by id."""
        async with self._lock:
            if task_id and task_id != self.active_task_id:
                if task_id in self._pending_task_ids:
                    self._pending_task_ids.remove(task_id)
                    task = self._tasks[task_id]
                    task.status = "stopped"
                    task.finished_at = datetime.now().isoformat()
                    task.error_message = "Cancelled before start"
                    await self._push_log(self._create_log_entry("Queued task cancelled.", "warning", task_id))
                    self._persist_tasks()
                    return True
                return False

            if not self.process or self.process.poll() is not None:
                return False

            active_task_id = self.active_task_id
            self.status = "stopping"
            if active_task_id and active_task_id in self._tasks:
                self._tasks[active_task_id].status = "stopping"
            entry = self._create_log_entry("Sending SIGTERM to crawler process...", "warning", active_task_id)
            await self._push_log(entry)

            try:
                self.process.send_signal(signal.SIGTERM)

                for _ in range(30):
                    if self.process.poll() is not None:
                        break
                    await asyncio.sleep(0.5)

                if self.process.poll() is None:
                    entry = self._create_log_entry("Process not responding, sending SIGKILL...", "warning", active_task_id)
                    await self._push_log(entry)
                    self.process.kill()

                entry = self._create_log_entry("Crawler process terminated", "info", active_task_id)
                await self._push_log(entry)

            except Exception as e:
                entry = self._create_log_entry(f"Error stopping crawler: {str(e)}", "error", active_task_id)
                await self._push_log(entry)

            if self._read_task:
                self._read_task.cancel()
                self._read_task = None

            await self._finalize_active_task(exit_code=self.process.returncode if self.process else -1, stopped=True)
            await self._start_next_pending()
            return True

    def get_status(self) -> dict:
        """Get current manager status."""
        return {
            "status": self.status,
            "active_task_id": self.active_task_id,
            "queued_count": len(self._pending_task_ids),
            "platform": self.current_config.platform.value if self.current_config else None,
            "crawler_type": self.current_config.crawler_type.value if self.current_config else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "error_message": None,
        }

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        return self._tasks.get(task_id)

    def get_task_logs(self, task_id: str, limit: int = 100) -> List[LogEntry]:
        logs = self._task_logs.get(task_id, [])
        return logs[-limit:] if limit > 0 else logs

    def _create_task(self, config: CrawlerStartRequest) -> TaskRecord:
        now = datetime.now()
        task_id = f"{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        safe_config = self._safe_config(config)
        return TaskRecord(
            id=task_id,
            name=config.task_name or self._get_default_task_name(config),
            status="queued",
            platform=config.platform.value,
            crawler_type=config.crawler_type.value,
            save_option=config.save_option.value,
            login_type=config.login_type.value,
            target=self._get_target(config),
            tags=config.tags,
            source_template_id=config.source_template_id,
            created_at=now.isoformat(),
            config=safe_config,
        )

    async def _launch_task(self, task_id: str) -> None:
        task = self._tasks[task_id]
        config = self._task_configs.get(task_id, task.config)
        cmd, redacted_cmd = self._build_command(config)

        self._clear_log_queue()
        self.active_task_id = task_id
        self.current_config = config
        self.started_at = datetime.now()
        self.status = "running"
        self._logs = self._task_logs.setdefault(task_id, [])
        self._task_file_snapshots[task_id] = self._snapshot_data_files()

        task.status = "running"
        task.started_at = self.started_at.isoformat()
        task.command = redacted_cmd
        self._persist_tasks()

        await self._push_log(self._create_log_entry(f"Starting crawler: {' '.join(redacted_cmd)}", "info", task_id))

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                bufsize=1,
                cwd=str(self._project_root),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

            await self._push_log(
                self._create_log_entry(
                    f"Crawler started on platform: {config.platform.value}, type: {config.crawler_type.value}",
                    "success",
                    task_id,
                )
            )

            self._read_task = asyncio.create_task(self._read_output(task_id))
        except Exception as e:
            self.process = None
            self.status = "error"
            task.status = "failed"
            task.error_message = str(e)
            task.finished_at = datetime.now().isoformat()
            await self._push_log(self._create_log_entry(f"Failed to start crawler: {str(e)}", "error", task_id))
            self._persist_tasks()
            await self._start_next_pending()

    async def _start_next_pending(self) -> None:
        if self.process and self.process.poll() is None:
            return
        if not self._pending_task_ids:
            return
        next_task_id = self._pending_task_ids.pop(0)
        await self._launch_task(next_task_id)

    async def _read_output(self, task_id: str):
        """Asynchronously read process output."""
        loop = asyncio.get_event_loop()

        try:
            while self.process and self.process.poll() is None:
                line = await loop.run_in_executor(None, self.process.stdout.readline)
                if line:
                    line = line.strip()
                    if line:
                        level = self._parse_log_level(line)
                        entry = self._create_log_entry(line, level, task_id)
                        await self._push_log(entry)

            if self.process and self.process.stdout:
                remaining = await loop.run_in_executor(None, self.process.stdout.read)
                if remaining:
                    for line in remaining.strip().split("\n"):
                        if line.strip():
                            level = self._parse_log_level(line)
                            entry = self._create_log_entry(line.strip(), level, task_id)
                            await self._push_log(entry)

            if self.active_task_id == task_id and self.status == "running":
                exit_code = self.process.returncode if self.process else -1
                if exit_code == 0:
                    entry = self._create_log_entry("Crawler completed successfully", "success", task_id)
                else:
                    entry = self._create_log_entry(f"Crawler exited with code: {exit_code}", "warning", task_id)
                await self._push_log(entry)
                await self._finalize_active_task(exit_code=exit_code)
                await self._start_next_pending()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            entry = self._create_log_entry(f"Error reading output: {str(e)}", "error", task_id)
            await self._push_log(entry)
            if self.active_task_id == task_id:
                await self._finalize_active_task(exit_code=-1)
                await self._start_next_pending()

    async def _finalize_active_task(self, exit_code: int, stopped: bool = False) -> None:
        task_id = self.active_task_id
        if task_id and task_id in self._tasks:
            task = self._tasks[task_id]
            task.exit_code = exit_code
            task.finished_at = datetime.now().isoformat()
            task.result_files = self._collect_result_files(task_id)
            task.logs_count = len(self._task_logs.get(task_id, []))
            if stopped:
                task.status = "stopped"
            elif exit_code == 0:
                task.status = "completed"
            else:
                task.status = "failed"

        self.status = "idle"
        self.current_config = None
        self.started_at = None
        self.active_task_id = None
        self.process = None
        self._logs = []
        self._persist_tasks()

    def _create_log_entry(self, message: str, level: str = "info", task_id: Optional[str] = None) -> LogEntry:
        """Create log entry and attach it to a task."""
        self._log_id += 1
        entry = LogEntry(
            id=self._log_id,
            task_id=task_id,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            message=message,
        )

        if task_id:
            task_logs = self._task_logs.setdefault(task_id, [])
            task_logs.append(entry)
            if len(task_logs) > 500:
                self._task_logs[task_id] = task_logs[-500:]
            if task_id in self._tasks:
                self._tasks[task_id].logs_count = len(self._task_logs[task_id])
        else:
            self._logs.append(entry)

        if task_id == self.active_task_id:
            self._logs = self._task_logs.get(task_id, [])

        return entry

    async def _push_log(self, entry: LogEntry):
        """Push log to queue."""
        if self._log_queue is not None:
            try:
                self._log_queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    def _clear_log_queue(self):
        if self._log_queue is None:
            self._log_queue = asyncio.Queue()
            return
        try:
            while True:
                self._log_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

    def _parse_log_level(self, line: str) -> str:
        """Parse log level."""
        line_upper = line.upper()
        if "ERROR" in line_upper or "FAILED" in line_upper:
            return "error"
        if "WARNING" in line_upper or "WARN" in line_upper:
            return "warning"
        if "SUCCESS" in line_upper or "完成" in line or "成功" in line:
            return "success"
        if "DEBUG" in line_upper:
            return "debug"
        return "info"

    def _build_command(self, config: CrawlerStartRequest) -> Tuple[list, list]:
        """Build main.py command line arguments and a redacted display command."""
        cmd = ["uv", "run", "python", "main.py"]

        cmd.extend(["--platform", config.platform.value])
        cmd.extend(["--lt", config.login_type.value])
        cmd.extend(["--type", config.crawler_type.value])
        cmd.extend(["--save_data_option", config.save_option.value])

        if config.crawler_type.value == "search" and config.keywords:
            cmd.extend(["--keywords", config.keywords])
            if config.platform.value == "xhs":
                cmd.extend(["--sort_type", config.sort_type.value])
        elif config.crawler_type.value == "detail" and config.specified_ids:
            cmd.extend(["--specified_id", config.specified_ids])
        elif config.crawler_type.value == "creator" and config.creator_ids:
            cmd.extend(["--creator_id", config.creator_ids])

        if config.start_page != 1:
            cmd.extend(["--start", str(config.start_page)])
        if config.max_notes_count:
            cmd.extend(["--max_notes_count", str(config.max_notes_count)])

        cmd.extend(["--get_comment", "true" if config.enable_comments else "false"])
        cmd.extend(["--get_sub_comment", "true" if config.enable_sub_comments else "false"])
        cmd.extend(["--cdp_connect_existing", "true" if config.cdp_connect_existing else "false"])
        cmd.extend(["--cdp_debug_port", str(config.cdp_debug_port)])

        if config.cookies:
            cmd.extend(["--cookies", config.cookies])

        cmd.extend(["--headless", "true" if config.headless else "false"])
        return cmd, self._redact_command(cmd)

    def _redact_command(self, cmd: list) -> list:
        redacted = list(cmd)
        for index, value in enumerate(redacted):
            if value == "--cookies" and index + 1 < len(redacted):
                redacted[index + 1] = "***"
        return redacted

    def _safe_config(self, config: CrawlerStartRequest) -> CrawlerStartRequest:
        return config.model_copy(update={"cookies": "***" if config.cookies else ""})

    def _get_default_task_name(self, config: CrawlerStartRequest) -> str:
        target = self._get_target(config)
        if target:
            short_target = target[:24] + ("..." if len(target) > 24 else "")
            return f"{config.platform.value.upper()} {config.crawler_type.value} - {short_target}"
        return f"{config.platform.value.upper()} {config.crawler_type.value}"

    def _get_target(self, config: CrawlerStartRequest) -> str:
        if config.crawler_type.value == "detail":
            return config.specified_ids
        if config.crawler_type.value == "creator":
            return config.creator_ids
        return config.keywords

    def _snapshot_data_files(self) -> set[str]:
        if not self._data_dir.exists():
            return set()
        supported_extensions = {".json", ".jsonl", ".csv", ".xlsx", ".xls"}
        ignored_files = {"webui_tasks.json", "webui_templates.json"}
        files = set()
        for path in self._data_dir.rglob("*"):
            if path.name in ignored_files:
                continue
            if path.is_file() and path.suffix.lower() in supported_extensions:
                files.add(str(path.relative_to(self._data_dir)))
        return files

    def _collect_result_files(self, task_id: str) -> List[str]:
        before = self._task_file_snapshots.get(task_id, set())
        after = self._snapshot_data_files()
        created = sorted(after - before)
        if created:
            return created
        return sorted(after, key=lambda item: (self._data_dir / item).stat().st_mtime, reverse=True)[:5]

    def _persist_tasks(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "tasks": [self._tasks[task_id].model_dump(mode="json") for task_id in self._task_order if task_id in self._tasks],
            "logs": {
                task_id: [entry.model_dump(mode="json") for entry in logs[-500:]]
                for task_id, logs in self._task_logs.items()
                if task_id in self._tasks
            },
        }
        self._tasks_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_tasks(self) -> None:
        if not self._tasks_file.exists():
            return

        try:
            payload = json.loads(self._tasks_file.read_text(encoding="utf-8"))
        except Exception:
            return

        for item in payload.get("tasks", [])[-100:]:
            try:
                task = TaskRecord.model_validate(item)
            except Exception:
                continue

            if task.status in {"queued", "running", "stopping"}:
                task.status = "failed"
                task.finished_at = task.finished_at or datetime.now().isoformat()
                task.error_message = "Server restarted before task finished"

            self._tasks[task.id] = task
            self._task_order.append(task.id)
            self._task_configs[task.id] = task.config

        for task_id, logs in payload.get("logs", {}).items():
            parsed_logs = []
            for entry in logs[-500:]:
                try:
                    parsed_logs.append(LogEntry.model_validate(entry))
                except Exception:
                    continue
            self._task_logs[task_id] = parsed_logs


# Global singleton
crawler_manager = CrawlerManager()
