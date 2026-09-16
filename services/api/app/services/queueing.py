from __future__ import annotations

from fastapi import BackgroundTasks
from ..config import get_settings
from .processing import process_document_by_id


def enqueue_document_processing(background_tasks: BackgroundTasks, document_id: str) -> None:
    settings = get_settings()
    if settings.app_env.lower() in {"production", "staging"}:
        from celery import Celery
        client = Celery(broker=settings.redis_url)
        client.send_task("docmind.document_processing", args=[document_id], queue="document-processing")
        return
    background_tasks.add_task(process_document_by_id, document_id)
