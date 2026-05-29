# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/crawler.py
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

from fastapi import APIRouter, HTTPException

from ..schemas import CrawlerStartRequest, CrawlerStatusResponse, TaskRecord
from ..services import crawler_manager

router = APIRouter(prefix="/crawler", tags=["crawler"])


@router.post("/start")
async def start_crawler(request: CrawlerStartRequest):
    """Start crawler task"""
    task = await crawler_manager.start(request)
    return {
        "status": "ok",
        "message": "Crawler task accepted",
        "task": task.model_dump(),
    }


@router.post("/stop")
async def stop_crawler(task_id: str | None = None):
    """Stop crawler task"""
    success = await crawler_manager.stop(task_id=task_id)
    if not success:
        raise HTTPException(status_code=400, detail="No matching running or queued crawler task")

    return {"status": "ok", "message": "Crawler stopped successfully"}


@router.get("/status", response_model=CrawlerStatusResponse)
async def get_crawler_status():
    """Get crawler status"""
    return crawler_manager.get_status()


@router.get("/logs")
async def get_logs(limit: int = 100):
    """Get recent logs"""
    logs = crawler_manager.logs[-limit:] if limit > 0 else crawler_manager.logs
    return {"logs": [log.model_dump() for log in logs]}


@router.get("/tasks", response_model=list[TaskRecord])
async def list_tasks(limit: int = 50):
    """Get crawler task history"""
    tasks = crawler_manager.tasks
    return tasks[:limit] if limit > 0 else tasks


@router.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str):
    """Get crawler task detail"""
    task = crawler_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks/{task_id}/logs")
async def get_task_logs(task_id: str, limit: int = 500):
    """Get logs for a crawler task"""
    if not crawler_manager.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    logs = crawler_manager.get_task_logs(task_id, limit=limit)
    return {"logs": [log.model_dump() for log in logs]}
