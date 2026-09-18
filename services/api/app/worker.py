from celery import Celery
from .config import get_settings
from .services.processing import process_document_by_id
from .services.exports import process_export_by_id

settings = get_settings()
celery = Celery("docmind", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "docmind.document_processing": {"queue": "document-processing"},
        "docmind.ocr": {"queue": "ocr"},
        "docmind.embedding": {"queue": "embedding"},
        "docmind.ai": {"queue": "ai"},
        "docmind.exports": {"queue": "exports"},
        "docmind.notifications": {"queue": "notifications"},
    },
)

@celery.task(name="docmind.document_processing", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def process_document(self, document_id: str) -> None:  # noqa: ANN001
    process_document_by_id(document_id)


@celery.task(name="docmind.exports", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=4)
def process_export(self, job_id: str) -> None:  # noqa: ANN001
    process_export_by_id(job_id)
