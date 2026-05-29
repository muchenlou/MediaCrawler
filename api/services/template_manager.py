# -*- coding: utf-8 -*-

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..schemas import CrawlerStartRequest, TemplateRecord, TemplateUpsertRequest


def _now() -> str:
    return datetime.now().isoformat()


def _config(**kwargs) -> CrawlerStartRequest:
    defaults = {
        "platform": "xhs",
        "login_type": "qrcode",
        "crawler_type": "search",
        "keywords": "",
        "specified_ids": "",
        "creator_ids": "",
        "start_page": 1,
        "enable_comments": True,
        "enable_sub_comments": False,
        "save_option": "jsonl",
        "cookies": "",
        "headless": False,
        "cdp_connect_existing": False,
        "cdp_debug_port": 9222,
    }
    defaults.update(kwargs)
    return CrawlerStartRequest.model_validate(defaults)


class TemplateManager:
    """Lightweight JSON-backed crawler template manager."""

    def __init__(self):
        self._project_root = Path(__file__).parent.parent.parent
        self._data_dir = self._project_root / "data"
        self._templates_file = self._data_dir / "webui_templates.json"
        self._templates: dict[str, TemplateRecord] = {}
        self._load_templates()

    @property
    def templates(self) -> List[TemplateRecord]:
        return sorted(self._templates.values(), key=lambda item: (item.category, item.name))

    def get(self, template_id: str) -> Optional[TemplateRecord]:
        return self._templates.get(template_id)

    def create(self, request: TemplateUpsertRequest) -> TemplateRecord:
        template_id = uuid.uuid4().hex[:12]
        now = _now()
        template = TemplateRecord(
            id=template_id,
            name=request.name,
            description=request.description,
            category=request.category,
            tags=request.tags,
            config=request.config.model_copy(update={"source_template_id": template_id}),
            created_at=now,
            updated_at=now,
        )
        self._templates[template.id] = template
        self._persist_templates()
        return template

    def update(self, template_id: str, request: TemplateUpsertRequest) -> Optional[TemplateRecord]:
        current = self._templates.get(template_id)
        if not current:
            return None

        template = TemplateRecord(
            id=template_id,
            name=request.name,
            description=request.description,
            category=request.category,
            tags=request.tags,
            config=request.config.model_copy(update={"source_template_id": template_id}),
            created_at=current.created_at,
            updated_at=_now(),
        )
        self._templates[template_id] = template
        self._persist_templates()
        return template

    def delete(self, template_id: str) -> bool:
        if template_id not in self._templates:
            return False
        del self._templates[template_id]
        self._persist_templates()
        return True

    def _load_templates(self) -> None:
        if not self._templates_file.exists():
            self._seed_defaults()
            self._persist_templates()
            return

        try:
            payload = json.loads(self._templates_file.read_text(encoding="utf-8"))
        except Exception:
            self._seed_defaults()
            return

        for item in payload.get("templates", []):
            try:
                template = TemplateRecord.model_validate(item)
            except Exception:
                continue
            self._templates[template.id] = template

        if not self._templates:
            self._seed_defaults()

    def _persist_templates(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "templates": [template.model_dump(mode="json") for template in self.templates],
        }
        self._templates_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _seed_defaults(self) -> None:
        now = _now()
        defaults = [
            TemplateRecord(
                id="xhs_keyword_monitor",
                name="小红书关键词监控",
                description="适合日常追踪竞品、品类词和内容趋势。",
                category="内容监控",
                tags=["小红书", "关键词", "评论"],
                config=_config(
                    task_name="小红书关键词监控",
                    tags=["内容监控", "小红书"],
                    source_template_id="xhs_keyword_monitor",
                    platform="xhs",
                    crawler_type="search",
                    keywords="品牌词,竞品词,行业词",
                    save_option="excel",
                ),
                created_at=now,
                updated_at=now,
            ),
            TemplateRecord(
                id="douyin_creator_watch",
                name="抖音达人主页采集",
                description="采集达人主页内容，用于投放或竞品账号观察。",
                category="达人观察",
                tags=["抖音", "达人", "主页"],
                config=_config(
                    task_name="抖音达人主页采集",
                    tags=["达人观察", "抖音"],
                    source_template_id="douyin_creator_watch",
                    platform="dy",
                    crawler_type="creator",
                    creator_ids="https://www.douyin.com/user/xxx",
                    save_option="jsonl",
                ),
                created_at=now,
                updated_at=now,
            ),
            TemplateRecord(
                id="weibo_keyword_pulse",
                name="微博舆情关键词",
                description="围绕关键词采集微博内容和评论。",
                category="舆情观察",
                tags=["微博", "舆情", "关键词"],
                config=_config(
                    task_name="微博舆情关键词",
                    tags=["舆情观察", "微博"],
                    source_template_id="weibo_keyword_pulse",
                    platform="wb",
                    crawler_type="search",
                    keywords="品牌词,事件词",
                    save_option="jsonl",
                ),
                created_at=now,
                updated_at=now,
            ),
            TemplateRecord(
                id="bili_video_detail",
                name="B站视频详情采集",
                description="按 BV 号或视频 URL 采集视频详情和评论。",
                category="内容详情",
                tags=["B站", "视频", "评论"],
                config=_config(
                    task_name="B站视频详情采集",
                    tags=["内容详情", "B站"],
                    source_template_id="bili_video_detail",
                    platform="bili",
                    crawler_type="detail",
                    specified_ids="BVxxxxxxxxxx",
                    save_option="excel",
                ),
                created_at=now,
                updated_at=now,
            ),
        ]

        self._templates = {template.id: template for template in defaults}


template_manager = TemplateManager()
