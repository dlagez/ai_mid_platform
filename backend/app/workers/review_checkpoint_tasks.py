from __future__ import annotations

import asyncio
from typing import Any

from app.db.session import SessionLocal
from app.review_checkpoints.service import ReviewCheckpointService
from app.utils.langfuse import flush_langfuse
from app.workers.celery_worker import celery_app


@celery_app.task(name="review_checkpoints.generate_from_clauses")
def generate_review_checkpoints_job(job_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return asyncio.run(ReviewCheckpointService().run_generation_job(db, job_id))
    finally:
        flush_langfuse()
        db.close()
