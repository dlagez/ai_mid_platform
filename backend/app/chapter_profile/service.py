from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.construction_ontology.service import recognize_construction_objects
from app.db.models import (
    ChapterProfileGenerationItem,
    ChapterProfileGenerationJob,
    ChapterReviewProfile,
    PlanDocument,
    PlanParseResult,
    PlanSection,
    ReviewTask,
)
from app.db.session import SessionLocal
from app.parsers.section_parse_strategies import DEFAULT_SECTION_PARSE_MODE, resolve_section_parse_mode
from app.services.model_service import ModelService
from app.utils.exceptions import PlatformError
from app.utils.langfuse import flush_langfuse, langfuse_observation, update_langfuse_observation


COMPLETED_GENERATION_ITEM_STATUSES = {"success", "rule_only"}
PROCESSED_GENERATION_ITEM_STATUSES = {"success", "rule_only", "failed", "cancelled"}
TERMINAL_GENERATION_JOB_STATUSES = {"success", "partial_success", "failed", "cancelled"}

PROFILE_EXTRACTION_PROMPT = """你是一名施工方案最小证据点抽取助手。

请基于施工方案章节标题和正文，抽取用于“规范规则点匹配”的最小方案证据点。

只输出 JSON，不要输出 Markdown，不要添加解释性文字。

重要原则：

1. evidence_points 必须是数组，因为一个章节中可能包含多个最小证据点。

2. evidence_text 必须来自施工方案原文，是可作为规范审查依据的最小方案证据点。

3. 最小证据点不是越短越好，而是应满足“一个独立审查语义 + 必要上下文”。

4. 如果两个短句属于同一施工场景、同一对象或同一参数约束，应合并为一个 evidence_text，避免失去上下文。
    例如：“每根立柱底部应设置垫板，垫板厚度不得小于50mm”应作为一个证据点，而不要拆成“设置垫板”和“垫板厚度50mm”两个孤立点。

5. 如果一个长句包含多个不同审查语义，应拆分为多个 evidence_text。
    例如“下层支架严禁拆除”和“上下层支架立柱位置对应”可合并为一个上层/下层支架场景证据点；“梁下立杆不对应时局部加设立杆”应单独作为一个证据点。

6. object_terms 必须来自章节标题或正文中的对象词，例如“立柱”“立杆”“扫地杆”“垫板”“上层支架”“下层支架”“水平拉杆”“剪刀撑”等。

7. object_terms 应尽量覆盖 evidence_text 中的核心审查对象，不要加入原文没有出现且无法直接推断的对象。

8. 不要判断是否符合规范，不要生成整改意见，不要引用规范条文，只抽取施工方案中已经写明的证据点。

9. confidence 为 0-1 小数，表示该证据点抽取可信度。

10. 如果章节正文中没有可审查的具体措施、参数、禁止项、条件项或对象关系，则 evidence_points 输出空数组。


拆分示例：
原文：
“每根立柱底部应设置垫板，垫板厚度不得小于50mm，支设上层支架时下层支架严禁拆除，且上层支架的立柱位置应与下层支架立柱位置对应。梁下立杆如有不对应情况，下层顶板立杆局部加设立杆，保证上下层立杆对应。”

应拆分为：

1. evidence_text: “每根立柱底部应设置垫板，垫板厚度不得小于50mm”
    object_terms: [“立柱底部”, “垫板”]

2. evidence_text: “支设上层支架时下层支架严禁拆除，且上层支架的立柱位置应与下层支架立柱位置对应”
    object_terms: [“上层支架”, “下层支架”, “上层支架立柱”, “下层支架立柱”]

3. evidence_text: “梁下立杆如有不对应情况，下层顶板立杆局部加设立杆，保证上下层立杆对应”
    object_terms: [“梁下立杆”, “下层顶板立杆”, “上下层立杆”]


输出格式必须严格为：
{
"evidence_points": [
{
"evidence_text": "",
"object_terms": [],
"confidence": 0.0
}
]
}

章节标题：
{title}

章节正文：
{content}
"""


class ChapterProfileService:
    async def build_profiles(self, db: Session, task_id: int) -> dict[str, Any]:
        task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
        if not task:
            raise PlatformError(f"Review task id={task_id} not found", status_code=404)
        return await self._build_profiles_for_document(db, document_id=task.plan_document_id, task_id=task.id)

    async def build_document_profiles(self, db: Session, document_id: int) -> dict[str, Any]:
        self._ensure_construction_plan_document(db, document_id)
        return await self._build_profiles_for_document(db, document_id=document_id, task_id=None)

    def create_generation_job(
        self,
        db: Session,
        document_id: int,
        section_parse_mode: str | None = None,
        concurrency: int = 6,
        created_by: int | None = None,
    ) -> ChapterProfileGenerationJob:
        document = self._ensure_construction_plan_document(db, document_id)
        mode = resolve_section_parse_mode(section_parse_mode or document.section_parse_mode or DEFAULT_SECTION_PARSE_MODE)
        result = (
            db.query(PlanParseResult)
            .filter(
                PlanParseResult.document_id == document.id,
                PlanParseResult.section_parse_mode == mode,
                PlanParseResult.parse_status == "parsed",
            )
            .first()
        )
        if not result:
            raise PlatformError(f"The document has no parsed sections for section_parse_mode={mode}.", status_code=400)
        sections = (
            db.query(PlanSection)
            .filter(
                PlanSection.document_id == document.id,
                PlanSection.parse_result_id == result.id,
            )
            .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
            .all()
        )
        target_sections = _filter_profile_target_sections(sections)
        if not target_sections:
            raise PlatformError("The parsed document has no leaf sections with non-empty content.", status_code=400)

        section_map = {section.id: section for section in sections}
        job = ChapterProfileGenerationJob(
            document_id=document.id,
            status="queued",
            total_sections=len(target_sections),
            created_by=created_by,
        )
        db.add(job)
        db.flush()
        for section in target_sections:
            db.add(
                ChapterProfileGenerationItem(
                    job_id=job.id,
                    document_id=document.id,
                    section_id=section.id,
                    section_title=section.title,
                    section_path=_build_chapter_path(section, section_map),
                    status="queued",
                )
            )
        db.commit()
        db.refresh(job)

        from app.workers.chapter_profile_tasks import generate_chapter_profiles_job

        async_result = generate_chapter_profiles_job.delay(job.id, max(1, min(concurrency, 8)))
        job.celery_task_id = async_result.id
        db.commit()
        db.refresh(job)
        return job

    def list_generation_jobs(
        self,
        db: Session,
        *,
        document_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ChapterProfileGenerationJob], int]:
        query = db.query(ChapterProfileGenerationJob)
        if document_id is not None:
            query = query.filter(ChapterProfileGenerationJob.document_id == document_id)
        if status:
            query = query.filter(ChapterProfileGenerationJob.status == status)
        total = query.count()
        items = (
            query.order_by(ChapterProfileGenerationJob.created_at.desc(), ChapterProfileGenerationJob.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_generation_job(self, db: Session, job_id: int) -> ChapterProfileGenerationJob:
        job = db.query(ChapterProfileGenerationJob).filter(ChapterProfileGenerationJob.id == job_id).first()
        if not job:
            raise PlatformError(f"Chapter profile generation job id={job_id} not found", status_code=404)
        return job

    def get_generation_job_sections(self, db: Session, job_id: int) -> tuple[PlanParseResult | None, list[PlanSection]]:
        job = self.get_generation_job(db, job_id)
        first_item = (
            db.query(ChapterProfileGenerationItem)
            .filter(ChapterProfileGenerationItem.job_id == job.id, ChapterProfileGenerationItem.section_id.isnot(None))
            .order_by(ChapterProfileGenerationItem.id.asc())
            .first()
        )
        if not first_item:
            return None, []
        first_section = db.query(PlanSection).filter(PlanSection.id == first_item.section_id).first()
        if not first_section:
            return None, []
        result = db.query(PlanParseResult).filter(PlanParseResult.id == first_section.parse_result_id).first()
        sections = (
            db.query(PlanSection)
            .filter(PlanSection.parse_result_id == first_section.parse_result_id)
            .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
            .all()
        )
        return result, sections

    def restart_generation_job(
        self,
        db: Session,
        job_id: int,
        concurrency: int = 6,
    ) -> ChapterProfileGenerationJob:
        job = self.get_generation_job(db, job_id)
        retryable_statuses = {"queued", "running", "failed"}
        items = (
            db.query(ChapterProfileGenerationItem)
            .filter(
                ChapterProfileGenerationItem.job_id == job.id,
                ChapterProfileGenerationItem.status.in_(retryable_statuses),
            )
            .all()
        )
        if not items:
            raise PlatformError("This chapter profile job has no unfinished or failed sections to restart.", status_code=400)

        now = datetime.utcnow()
        for item in items:
            item.status = "queued"
            item.profile_id = None
            item.used_llm = False
            item.confidence = None
            item.message = "Requeued for restart."
            item.started_at = None
            item.finished_at = None
            item.updated_at = now

        job.status = "queued"
        job.error_message = None
        job.started_at = None
        job.finished_at = None
        job.updated_at = now
        self._refresh_generation_job_summary(db, job)
        db.commit()

        from app.workers.chapter_profile_tasks import generate_chapter_profiles_job

        async_result = generate_chapter_profiles_job.delay(job.id, max(1, min(concurrency, 8)))
        job.celery_task_id = async_result.id
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return job

    def pause_generation_job(self, db: Session, job_id: int) -> ChapterProfileGenerationJob:
        job = self.get_generation_job(db, job_id)
        if job.status not in {"queued", "running"}:
            raise PlatformError("Only queued or running chapter profile jobs can be paused.", status_code=400)

        now = datetime.utcnow()
        (
            db.query(ChapterProfileGenerationItem)
            .filter(
                ChapterProfileGenerationItem.job_id == job.id,
                ChapterProfileGenerationItem.status == "queued",
            )
            .update(
                {
                    "status": "paused",
                    "message": "Paused.",
                    "updated_at": now,
                },
                synchronize_session=False,
            )
        )
        job.status = "paused"
        job.updated_at = now
        self._refresh_generation_job_summary(db, job)
        db.commit()
        db.refresh(job)
        return job

    def resume_generation_job(
        self,
        db: Session,
        job_id: int,
        concurrency: int = 6,
    ) -> ChapterProfileGenerationJob:
        job = self.get_generation_job(db, job_id)
        if job.status != "paused":
            raise PlatformError("Only paused chapter profile jobs can be continued.", status_code=400)

        now = datetime.utcnow()
        (
            db.query(ChapterProfileGenerationItem)
            .filter(
                ChapterProfileGenerationItem.job_id == job.id,
                ChapterProfileGenerationItem.status == "paused",
            )
            .update(
                {
                    "status": "queued",
                    "message": "Requeued for continue.",
                    "updated_at": now,
                },
                synchronize_session=False,
            )
        )
        job.status = "queued"
        job.error_message = None
        job.finished_at = None
        job.updated_at = now
        self._refresh_generation_job_summary(db, job)
        db.commit()

        from app.workers.chapter_profile_tasks import generate_chapter_profiles_job

        async_result = generate_chapter_profiles_job.delay(job.id, max(1, min(concurrency, 8)))
        job.celery_task_id = async_result.id
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return job

    def cancel_generation_job(self, db: Session, job_id: int) -> ChapterProfileGenerationJob:
        job = self.get_generation_job(db, job_id)
        if job.status in TERMINAL_GENERATION_JOB_STATUSES:
            raise PlatformError("This chapter profile job is already finished.", status_code=400)

        now = datetime.utcnow()
        (
            db.query(ChapterProfileGenerationItem)
            .filter(
                ChapterProfileGenerationItem.job_id == job.id,
                ChapterProfileGenerationItem.status.notin_(COMPLETED_GENERATION_ITEM_STATUSES),
            )
            .update(
                {
                    "status": "cancelled",
                    "message": "Cancelled.",
                    "finished_at": now,
                    "updated_at": now,
                },
                synchronize_session=False,
            )
        )
        job.status = "cancelled"
        job.error_message = None
        job.finished_at = now
        job.updated_at = now
        self._refresh_generation_job_summary(db, job)
        db.commit()
        db.refresh(job)
        return job

    def list_generation_items(
        self,
        db: Session,
        *,
        job_id: int,
        status: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[ChapterProfileGenerationItem], int]:
        self.get_generation_job(db, job_id)
        query = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.job_id == job_id)
        if status:
            query = query.filter(ChapterProfileGenerationItem.status == status)
        total = query.count()
        items = (
            query.order_by(ChapterProfileGenerationItem.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_generation_profiles(
        self,
        db: Session,
        *,
        job_id: int,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[ChapterReviewProfile], int]:
        job = self.get_generation_job(db, job_id)
        section_ids = [
            section_id
            for (section_id,) in (
                db.query(ChapterProfileGenerationItem.section_id)
                .filter(
                    ChapterProfileGenerationItem.job_id == job_id,
                    ChapterProfileGenerationItem.section_id.isnot(None),
                )
                .all()
            )
            if section_id is not None
        ]
        if not section_ids:
            return [], 0
        query = (
            db.query(ChapterReviewProfile)
            .filter(
                ChapterReviewProfile.document_id == job.document_id,
                ChapterReviewProfile.section_id.in_(section_ids),
                ChapterReviewProfile.status == "active",
            )
        )
        if job.task_id is None:
            query = query.filter(ChapterReviewProfile.task_id.is_(None))
        else:
            query = query.filter(ChapterReviewProfile.task_id == job.task_id)
        total = query.count()
        items = (
            query.order_by(ChapterReviewProfile.section_id.asc(), ChapterReviewProfile.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    async def run_generation_job(self, db: Session, job_id: int, concurrency: int = 1) -> dict[str, Any]:
        job = self.get_generation_job(db, job_id)
        if job.status in TERMINAL_GENERATION_JOB_STATUSES or job.status == "paused":
            return {"job_id": job.id, "status": job.status}

        job.status = "running"
        job.started_at = job.started_at or datetime.utcnow()
        job.updated_at = datetime.utcnow()
        db.commit()

        try:
            item_ids = [
                item.id
                for item in (
                    db.query(ChapterProfileGenerationItem)
                    .filter(ChapterProfileGenerationItem.job_id == job.id)
                    .order_by(ChapterProfileGenerationItem.id.asc())
                    .all()
                )
                if item.status == "queued"
            ]
            semaphore = asyncio.Semaphore(max(1, min(concurrency, 8)))

            async def run_item(item_id: int) -> None:
                async with semaphore:
                    await self._run_generation_item(job_id, item_id)

            await asyncio.gather(*(run_item(item_id) for item_id in item_ids))
            db.expire_all()
            job = self.get_generation_job(db, job_id)
            self._refresh_generation_job_summary(db, job)
            if job.status == "cancelled":
                job.updated_at = datetime.utcnow()
                db.commit()
                flush_langfuse()
                return {"job_id": job.id, "status": job.status}
            if job.status == "paused" and job.processed_sections < job.total_sections:
                job.finished_at = None
                job.updated_at = datetime.utcnow()
                db.commit()
                flush_langfuse()
                return {"job_id": job.id, "status": job.status}
            if job.processed_sections < job.total_sections:
                job.finished_at = None
                job.updated_at = datetime.utcnow()
                db.commit()
                flush_langfuse()
                return {"job_id": job.id, "status": job.status}
            job.finished_at = datetime.utcnow()
            if job.failed_count >= job.total_sections:
                job.status = "failed"
            elif job.failed_count > 0 or job.rule_only_count > 0:
                job.status = "partial_success"
            else:
                job.status = "success"
            job.updated_at = datetime.utcnow()
            db.commit()
            flush_langfuse()
            return {"job_id": job.id, "status": job.status}
        except Exception as exc:
            db.rollback()
            job = self.get_generation_job(db, job_id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            db.commit()
            flush_langfuse()
            raise

    async def _run_generation_item(self, job_id: int, item_id: int) -> None:
        db = SessionLocal()
        try:
            job = self.get_generation_job(db, job_id)
            item = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.id == item_id).first()
            if not item or job.status in {"paused", "cancelled"}:
                return

            now = datetime.utcnow()
            claimed_count = (
                db.query(ChapterProfileGenerationItem)
                .filter(
                    ChapterProfileGenerationItem.id == item_id,
                    ChapterProfileGenerationItem.status == "queued",
                )
                .update(
                    {
                        "status": "running",
                        "started_at": item.started_at or now,
                        "updated_at": now,
                    },
                    synchronize_session=False,
                )
            )
            db.commit()
            if not claimed_count:
                return
            db.expire_all()
            job = self.get_generation_job(db, job_id)
            item = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.id == item_id).first()
            if not item or job.status in {"paused", "cancelled"}:
                return


            plan_section = (
                db.query(PlanSection)
                .join(PlanParseResult, PlanParseResult.id == PlanSection.parse_result_id)
                .filter(
                    PlanSection.document_id == job.document_id,
                    PlanSection.id == item.section_id,
                    PlanParseResult.parse_status == "parsed",
                )
                .first()
            )
            if not plan_section:
                item.status = "failed"
                item.message = "Section not found."
                item.finished_at = datetime.utcnow()
                item.updated_at = datetime.utcnow()
                self._refresh_generation_job_summary(db, job)
                db.commit()
                return

            section_map = {
                section.id: section
                for section in (
                    db.query(PlanSection)
                    .filter(PlanSection.parse_result_id == plan_section.parse_result_id)
                    .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
                    .all()
                )
            }
            profiles, created_count, updated_count, llm_failed = await self._upsert_profiles_for_section(
                db,
                section=plan_section,
                section_map=section_map,
                document_id=job.document_id,
                task_id=job.task_id,
                job_id=job.id,
            )
            db.expire(job)
            job = self.get_generation_job(db, job_id)
            if job.status == "cancelled":
                db.rollback()
                item = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.id == item_id).first()
                if item:
                    item.status = "cancelled"
                    item.message = "Cancelled."
                    item.finished_at = datetime.utcnow()
                    item.updated_at = datetime.utcnow()
                self._refresh_generation_job_summary(db, job)
                db.commit()
                return
            item.status = "rule_only" if llm_failed else "success"
            item.profile_id = profiles[0].id if profiles else None
            item.used_llm = not llm_failed
            item.confidence = _average_confidence(profiles)
            if llm_failed:
                item.message = f"Profiles created={created_count}, updated={updated_count}; LLM failed, rule-only profile saved."
            else:
                item.message = f"Profiles created={created_count}, updated={updated_count}."
            item.finished_at = datetime.utcnow()
            item.updated_at = datetime.utcnow()
            self._refresh_generation_job_summary(db, job)
            db.commit()
        except Exception as exc:
            db.rollback()
            job = self.get_generation_job(db, job_id)
            item = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.id == item_id).first()
            if item:
                item.status = "failed"
                item.message = str(exc)
                item.finished_at = datetime.utcnow()
                item.updated_at = datetime.utcnow()
            self._refresh_generation_job_summary(db, job)
            db.commit()
        finally:
            db.close()

    async def _build_profiles_for_document(self, db: Session, *, document_id: int, task_id: int | None) -> dict[str, Any]:
        sections = (
            db.query(PlanSection)
            .join(PlanParseResult, PlanParseResult.id == PlanSection.parse_result_id)
            .join(PlanDocument, PlanDocument.id == PlanSection.document_id)
            .filter(
                PlanSection.document_id == document_id,
                PlanParseResult.section_parse_mode == PlanDocument.section_parse_mode,
                PlanParseResult.parse_status == "parsed",
            )
            .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
            .all()
        )
        sections_to_profile = _filter_profile_target_sections(sections)
        if not sections_to_profile:
            raise PlatformError("The review task document has no leaf sections with non-empty content.", status_code=400)

        section_map = {section.id: section for section in sections}
        created_count = 0
        updated_count = 0
        failed: list[dict[str, Any]] = []
        saved: list[ChapterReviewProfile] = []

        for section in sections_to_profile:
            try:
                profiles, section_created_count, section_updated_count, llm_failed = await self._upsert_profiles_for_section(
                    db,
                    section=section,
                    section_map=section_map,
                    document_id=document_id,
                    task_id=task_id,
                )
                created_count += section_created_count
                updated_count += section_updated_count
                if llm_failed:
                    failed.append({"section_id": section.id, "reason": "LLM failed; rule-only profile saved."})
                saved.extend(profiles)
            except Exception as exc:
                failed.append({"section_id": section.id, "reason": str(exc)})
        db.commit()
        for row in saved:
            db.refresh(row)
        return {
            "task_id": task_id,
            "document_id": document_id,
            "created_count": created_count,
            "updated_count": updated_count,
            "failed": failed,
            "items": saved,
        }

    async def _upsert_profiles_for_section(
        self,
        db: Session,
        *,
        section: PlanSection,
        section_map: dict[int, PlanSection],
        document_id: int,
        task_id: int | None,
        job_id: int | None = None,
    ) -> tuple[list[ChapterReviewProfile], int, int, bool]:
        text = f"{section.title}\n{section.content or ''}"
        objects = recognize_construction_objects(db, text)
        object_terms = _object_terms(objects)

        ai_data: dict[str, Any] = {}
        llm_failed = False
        try:
            ai_data = await self._extract_profile_by_llm(section, job_id=job_id, document_id=document_id)
        except Exception:
            llm_failed = True

        chapter_path = _build_chapter_path(section, section_map)
        evidence_points = _evidence_points_from_ai_data(ai_data)
        if llm_failed:
            evidence_points = [_fallback_evidence_point(section)]

        query = db.query(ChapterReviewProfile).filter(
            ChapterReviewProfile.document_id == document_id,
            ChapterReviewProfile.section_id == section.id,
        )
        if task_id is None:
            query = query.filter(ChapterReviewProfile.task_id.is_(None))
        else:
            query = query.filter(ChapterReviewProfile.task_id == task_id)

        existing_rows = query.order_by(ChapterReviewProfile.id.asc()).all()
        existing_by_text = {row.evidence_text: row for row in existing_rows}
        active_rows: list[ChapterReviewProfile] = []
        used_ids: set[int] = set()
        created_count = 0
        updated_count = 0
        now = datetime.utcnow()

        for index, point in enumerate(evidence_points, start=1):
            evidence_text = point["evidence_text"]
            row = existing_by_text.get(evidence_text)
            values = {
                "evidence_code": _default_evidence_code(section, index=index),
                "evidence_text": evidence_text,
                "object_terms": _merge_lists(object_terms, point.get("object_terms")),
                "task_id": task_id,
                "document_id": document_id,
                "section_id": section.id,
                "chapter_title": section.title,
                "chapter_path": chapter_path,
                "source_text": _source_text_for_evidence(section, evidence_text),
                "confidence": point["confidence"],
                "status": "active",
                "updated_at": now,
            }
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
                updated_count += 1
            else:
                row = ChapterReviewProfile(**values)
                db.add(row)
                created_count += 1
            db.flush()
            active_rows.append(row)
            used_ids.add(row.id)

        for row in existing_rows:
            if row.id not in used_ids and row.status == "active":
                row.status = "inactive"
                row.updated_at = now
        db.flush()
        return active_rows, created_count, updated_count, llm_failed

    def _ensure_construction_plan_document(self, db: Session, document_id: int) -> PlanDocument:
        document = db.query(PlanDocument).filter(PlanDocument.id == document_id).first()
        if not document:
            raise PlatformError(f"Document id={document_id} not found", status_code=404)
        if document.document_type != "construction_plan":
            raise PlatformError("Chapter profiles can only be generated for construction plan documents.", status_code=400)
        return document

    def _refresh_generation_job_summary(self, db: Session, job: ChapterProfileGenerationJob) -> None:
        items = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.job_id == job.id).all()
        job.processed_sections = sum(1 for item in items if item.status in PROCESSED_GENERATION_ITEM_STATUSES)
        job.created_count = sum(_message_count(item.message, "created") for item in items if item.status in {"success", "rule_only"})
        job.updated_count = sum(_message_count(item.message, "updated") for item in items if item.status in {"success", "rule_only"})
        job.failed_count = sum(1 for item in items if item.status == "failed")
        job.rule_only_count = sum(1 for item in items if item.status == "rule_only")
        job.updated_at = datetime.utcnow()

    async def _extract_profile_by_llm(
        self,
        section: PlanSection,
        *,
        job_id: int | None = None,
        document_id: int | None = None,
    ) -> dict[str, Any]:
        content = (section.content or "")[:4000]
        if not content.strip():
            return {}
        model_service = ModelService()
        prompt = PROFILE_EXTRACTION_PROMPT.replace("{title}", section.title or "").replace("{content}", content)
        payload = {
            "model": model_service.default_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
        }
        metadata = {
            "operation": "chapter_profile.extract",
            "job_id": job_id,
            "document_id": document_id or section.document_id,
            "section_id": section.id,
            "section_title": section.title,
            "content_chars": len(content),
        }
        with langfuse_observation(
            name="chapter_profile.extract",
            input_data={"messages": payload["messages"]},
            metadata=metadata,
            session_id=f"chapter-profile-job:{job_id}" if job_id else f"chapter-profile-document:{document_id or section.document_id}",
            tags=["chapter_profile", "llm"],
            as_type="generation",
            model=model_service.default_model,
        ) as observation:
            result = await model_service.call_model(payload)
            output_content = ((result.get("output") or {}).get("content") or "").strip()
            update_langfuse_observation(
                observation,
                output={"content": output_content},
                metadata=metadata | {"output_chars": len(output_content)},
            )
        return _parse_json_object(output_content)


def _filter_profile_target_sections(sections: list[PlanSection]) -> list[PlanSection]:
    parent_ids = {section.parent_id for section in sections if section.parent_id is not None}
    return [
        section
        for section in sections
        if section.id not in parent_ids and (section.content or "").strip()
    ]


def _build_chapter_path(section: PlanSection, section_map: dict[int, PlanSection]) -> str:
    parts: list[str] = []
    current: PlanSection | None = section
    guard = 0
    while current and guard < 20:
        title = current.title or ""
        if current.section_no:
            title = f"{current.section_no} {title}"
        parts.append(title.strip())
        current = section_map.get(current.parent_id) if current.parent_id else None
        guard += 1
    return " / ".join(reversed([part for part in parts if part]))


def _object_terms(objects: list[dict[str, Any]]) -> list[str]:
    values = []
    for item in objects:
        values.append(str(item.get("object_name") or ""))
        values.extend(str(term) for term in item.get("matched_terms") or [])
    return _merge_lists(values)


def _fallback_evidence_point(section: PlanSection) -> dict[str, Any]:
    return {
        "evidence_text": _fallback_evidence_text(section),
        "object_terms": [],
        "confidence": 0.0,
    }


def _fallback_evidence_text(section: PlanSection) -> str:
    content = (section.content or "").strip()
    if not content:
        return section.title or ""
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), content)
    return first_line[:500]


def _fallback_source_text(section: PlanSection) -> str:
    content = (section.content or "").strip()
    return content[:1000] if content else (section.title or "")


def _source_text_for_evidence(section: PlanSection, evidence_text: str) -> str:
    content = (section.content or "").strip()
    evidence = evidence_text.strip()
    if not content or not evidence:
        return _fallback_source_text(section)

    for segment in _iter_source_segments(content):
        if evidence in segment:
            return segment[:1000]

    normalized_evidence = _normalize_text_for_match(evidence)
    if normalized_evidence:
        for segment in _iter_source_segments(content):
            if normalized_evidence in _normalize_text_for_match(segment):
                return segment[:1000]

    return _fallback_source_text(section)


def _iter_source_segments(content: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", content) if part.strip()]
    line_segments = [line.strip() for line in content.splitlines() if line.strip()]
    sentence_segments = _split_source_sentences(content)
    return _merge_lists(sentence_segments, line_segments, paragraphs)


def _split_source_sentences(content: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(content):
        if char == ".":
            previous_char = content[index - 1] if index > 0 else ""
            next_char = content[index + 1] if index + 1 < len(content) else ""
            if previous_char.isdigit() and next_char.isdigit():
                continue
        elif char not in "。！？；!?;":
            continue

        sentence = content[start : index + 1].strip()
        if sentence:
            sentences.append(sentence)
        start = index + 1

    tail = content[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _normalize_text_for_match(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _default_evidence_code(section: PlanSection, *, index: int = 1) -> str:
    section_no = re.sub(r"[^A-Za-z0-9]+", "-", section.section_no or str(section.id)).strip("-")
    return f"E-{section_no or section.id}-{index:03d}"


def _evidence_points_from_ai_data(ai_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_points = ai_data.get("evidence_points")
    if raw_points is None and ai_data.get("evidence_text"):
        raw_points = [ai_data]
    if not isinstance(raw_points, list):
        return []

    points: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_point in raw_points:
        if not isinstance(raw_point, dict):
            continue
        evidence_text = _as_string(raw_point.get("evidence_text"))
        if not evidence_text or evidence_text in seen:
            continue
        seen.add(evidence_text)
        points.append(
            {
                "evidence_text": evidence_text,
                "object_terms": _as_list(raw_point.get("object_terms")),
                "confidence": _as_confidence(raw_point.get("confidence"), default=0.0),
            }
        )
    return points


def _average_confidence(profiles: list[ChapterReviewProfile]) -> float | None:
    values = [float(profile.confidence) for profile in profiles if profile.confidence is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _message_count(message: str | None, key: str) -> int:
    if not message:
        return 0
    match = re.search(rf"{re.escape(key)}=(\d+)", message)
    return int(match.group(1)) if match else 0


def _as_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]


def _merge_lists(*values: Any) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in values:
        iterable = value if isinstance(value, (list, tuple, set, Generator)) else [value]
        for item in iterable:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _as_confidence(value: Any, *, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _parse_json_object(content: str) -> dict[str, Any]:
    if not content:
        raise PlatformError("LLM returned empty content.", status_code=502)
    cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise PlatformError("LLM output is not a JSON object.", status_code=502)
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise PlatformError("LLM output JSON must be an object.", status_code=502)
    return parsed


def get_chapter_profile_service() -> Generator[ChapterProfileService, None, None]:
    yield ChapterProfileService()
