# -*- coding: utf-8 -*-

from fastapi import APIRouter, HTTPException

from ..schemas import CrawlerStartRequest, TemplateRecord, TemplateUpsertRequest
from ..services import crawler_manager
from ..services.template_manager import template_manager

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateRecord])
async def list_templates():
    """Get reusable crawler templates."""
    return template_manager.templates


@router.post("", response_model=TemplateRecord)
async def create_template(request: TemplateUpsertRequest):
    """Create a reusable crawler template."""
    return template_manager.create(request)


@router.put("/{template_id}", response_model=TemplateRecord)
async def update_template(template_id: str, request: TemplateUpsertRequest):
    """Update a reusable crawler template."""
    template = template_manager.update(template_id, request)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """Delete a reusable crawler template."""
    if not template_manager.delete(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "ok", "message": "Template deleted"}


@router.post("/{template_id}/run")
async def run_template(template_id: str, override: CrawlerStartRequest | None = None):
    """Run a template. Optional body can override the stored config."""
    template = template_manager.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    config = override or template.config
    if not config.source_template_id:
        config = config.model_copy(update={"source_template_id": template_id})
    if not config.task_name:
        config = config.model_copy(update={"task_name": template.name})

    task = await crawler_manager.start(config)
    return {
        "status": "ok",
        "message": "Template task accepted",
        "task": task.model_dump(),
    }
