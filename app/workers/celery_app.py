from celery import Celery # type: ignore
from app.core.config import settings


celery_app = Celery(
    "autoapply",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.auto_apply_task"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Reliability
    task_track_started=True,
    task_acks_late=True,           # re-queue task if worker crashes mid-execution
    worker_prefetch_multiplier=1,  # one task at a time per worker — Playwright is heavy

    # Results
    result_expires=86400,          # keep results for 24 hours
)