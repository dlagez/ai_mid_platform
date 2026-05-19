from time import sleep
from typing import Any

from celery import Celery

from configs.settings import settings

celery_app = Celery(
    "ai_mid_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task(name="platform.run_task")
def run_platform_task(task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    sleep(1)
    return {"task_type": task_type, "payload": payload, "message": "Task completed"}


from app.workers import ppocr_pdf_tasks  # noqa: E402,F401
