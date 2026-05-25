from __future__ import annotations

import asyncio

from app.chapter_profile.service import ChapterProfileService
from app.db.session import SessionLocal
from app.workers.celery_worker import celery_app


@celery_app.task(name="chapter_profiles.generate_for_document")
def generate_chapter_profiles_job(job_id: int) -> dict:
    db = SessionLocal()
    try:
        return asyncio.run(ChapterProfileService().run_generation_job(db, job_id))
    finally:
        db.close()
