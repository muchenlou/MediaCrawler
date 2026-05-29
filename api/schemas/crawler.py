# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/schemas/crawler.py
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

from enum import Enum
from typing import Optional, Literal, List
from pydantic import BaseModel


class PlatformEnum(str, Enum):
    """Supported media platforms"""
    XHS = "xhs"
    DOUYIN = "dy"
    KUAISHOU = "ks"
    BILIBILI = "bili"
    WEIBO = "wb"
    TIEBA = "tieba"
    ZHIHU = "zhihu"


class LoginTypeEnum(str, Enum):
    """Login method"""
    QRCODE = "qrcode"
    PHONE = "phone"
    COOKIE = "cookie"


class CrawlerTypeEnum(str, Enum):
    """Crawler type"""
    SEARCH = "search"
    DETAIL = "detail"
    CREATOR = "creator"


class SaveDataOptionEnum(str, Enum):
    """Data save option"""
    CSV = "csv"
    DB = "db"
    JSON = "json"
    JSONL = "jsonl"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    EXCEL = "excel"


class SearchSortTypeEnum(str, Enum):
    """Search result sort type"""
    GENERAL = "general"
    MOST_POPULAR = "popularity_descending"
    LATEST = "time_descending"


class CrawlerStartRequest(BaseModel):
    """Crawler start request"""
    task_name: str = ""
    tags: List[str] = []
    source_template_id: str = ""
    platform: PlatformEnum
    login_type: LoginTypeEnum = LoginTypeEnum.QRCODE
    crawler_type: CrawlerTypeEnum = CrawlerTypeEnum.SEARCH
    keywords: str = ""  # Keywords for search mode
    specified_ids: str = ""  # Post/video ID list for detail mode, comma-separated
    creator_ids: str = ""  # Creator ID list for creator mode, comma-separated
    sort_type: SearchSortTypeEnum = SearchSortTypeEnum.LATEST
    max_notes_count: int = 20
    start_page: int = 1
    enable_comments: bool = True
    enable_sub_comments: bool = False
    save_option: SaveDataOptionEnum = SaveDataOptionEnum.JSONL
    cookies: str = ""
    headless: bool = False
    cdp_connect_existing: bool = False
    cdp_debug_port: int = 9222


class CrawlerStatusResponse(BaseModel):
    """Crawler status response"""
    status: Literal["idle", "running", "stopping", "error"]
    active_task_id: Optional[str] = None
    queued_count: int = 0
    platform: Optional[str] = None
    crawler_type: Optional[str] = None
    started_at: Optional[str] = None
    error_message: Optional[str] = None


class LogEntry(BaseModel):
    """Log entry"""
    id: int
    task_id: Optional[str] = None
    timestamp: str
    level: Literal["info", "warning", "error", "success", "debug"]
    message: str


class TaskRecord(BaseModel):
    """Crawler task record"""
    id: str
    name: str = ""
    status: Literal["queued", "running", "stopping", "completed", "failed", "stopped"]
    platform: str
    crawler_type: str
    save_option: str
    login_type: str
    target: str = ""
    tags: List[str] = []
    source_template_id: str = ""
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    command: List[str] = []
    result_files: List[str] = []
    logs_count: int = 0
    error_message: Optional[str] = None
    config: CrawlerStartRequest


class TemplateRecord(BaseModel):
    """Reusable crawler task template"""
    id: str
    name: str
    description: str = ""
    category: str = "通用"
    tags: List[str] = []
    config: CrawlerStartRequest
    created_at: str
    updated_at: str


class TemplateUpsertRequest(BaseModel):
    """Create or update a crawler template"""
    name: str
    description: str = ""
    category: str = "通用"
    tags: List[str] = []
    config: CrawlerStartRequest


class DataFileInfo(BaseModel):
    """Data file information"""
    name: str
    path: str
    size: int
    modified_at: str
    record_count: Optional[int] = None
