from __future__ import annotations

import asyncio
import io
import json
import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.db.models import (
    ReviewCheckpoint,
    ReviewCheckpointGenerationItem,
    ReviewCheckpointGenerationJob,
    StandardClause,
    StandardDocument,
)
from app.db.session import SessionLocal
from app.review_checkpoints.schemas import (
    GenerateCheckpointsFromClausesRequest,
    ManualCheckpointImportRequest,
    ReviewCheckpointCreate,
    ReviewCheckpointUpdate,
)
from app.services.model_service import ModelService
from app.utils.exceptions import PlatformError
from app.utils.langfuse import langfuse_observation, update_langfuse_observation


CHECKPOINT_STATUSES = {"draft", "active", "disabled", "archived"}
GENERATION_JOB_STATUSES = {"queued", "running", "success", "partial_success", "failed"}
DEFAULT_GENERATION_CONCURRENCY = 5
MAX_GENERATION_CONCURRENCY = 10

CHECKPOINT_PROMPT = """你是一名施工规范最小审查点抽取助手。

请基于 内容，抽取用于“施工方案证据点匹配”的最小规范审查点。

只输出单行紧凑 JSON，不要输出 Markdown，不要添加解释性文字，不要换行，不要缩进，不要使用代码块。

内容：{clause_title}{clause_content}

重要原则：

1. checkpoints 必须是数组。
2. rule_text 必须来自规范原文，是可用于审查施工方案的最小规范审查点。
3. 最小审查点不是越短越好，而是应满足“一个独立审查语义 + 必要上下文”。
4. object_terms 必须来自条文标题或原文中的对象词。
5. 不要判断施工方案是否符合规范，不要生成整改意见，只抽取规范中已经写明的审查点。
6. confidence 为 0-1 小数，表示该审查点抽取可信度。
7. 如果条文中没有可审查的具体要求、禁止项、条件项、参数或对象关系，则 checkpoints 输出空数组。
8. 每个rule_text为原文其中一段，且不允许重复，所有的rule_text连起来等于原文。
9. 如果有表格，则每一行作为一个checkpoints、rule_text

拆分示例：
原文：
“立柱接长严禁搭接，必须采用对接扣件连接，相邻两立柱的对接接头不得在同步内，且对接接头沿竖向错开的距离不宜小于 500mm，各接头中心距主节点不宜大于步距的 1/3。模板支架可调托撑伸出顶层水平杆的悬臂长度严禁超过 650mm。”

步骤：1、原文拆分成2个rule_text，每个rule_text独立且不会重复，且每个rule_text语义独立，下一句话不会有上一句话的相关内容。2、抽取rule_text中的对象词。

1. rule_text: “立柱接长严禁搭接，必须采用对接扣件连接，相邻两立柱的对接接头不得在同步内，且对接接头沿竖向错开的距离不宜小于 500mm，各接头中心距主节点不宜大于步距的 1/3”
    object_terms: [“立柱”, “对接扣件”, “对接接头”, “主节点”, “步距”]

2. rule_text: “模板支架可调托撑伸出顶层水平杆的悬臂长度严禁超过 650mm”
    object_terms: [“模板支架”, “可调托撑”, “顶层水平杆”, “悬臂长度”]

输出格式必须严格为单行 JSON：
{"checkpoints":[{"rule_text":"","object_terms":[],"confidence":0.0}]}
"""


class ReviewCheckpointService:
    def list_checkpoints(
        self,
        db: Session,
        *,
        standard_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewCheckpoint], int]:
        query = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.status != "archived")
        if standard_id:
            query = query.filter(ReviewCheckpoint.standard_id == standard_id)
        if status:
            query = query.filter(ReviewCheckpoint.status == status)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    ReviewCheckpoint.rule_code.ilike(like),
                    ReviewCheckpoint.rule_text.ilike(like),
                    ReviewCheckpoint.clause_text.ilike(like),
                    cast(ReviewCheckpoint.object_terms, String).ilike(like),
                )
            )
        total = query.count()
        items = (
            query.order_by(ReviewCheckpoint.created_at.desc(), ReviewCheckpoint.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_checkpoint_tree(
        self,
        db: Session,
        *,
        standard_id: int,
        status: str | None = None,
        keyword: str | None = None,
    ) -> tuple[StandardDocument, list[StandardClause], list[ReviewCheckpoint]]:
        standard = db.query(StandardDocument).filter(StandardDocument.id == standard_id).first()
        if not standard or standard.status == "archived":
            raise PlatformError(f"Standard document id={standard_id} not found", status_code=404)

        clauses = (
            db.query(StandardClause)
            .filter(StandardClause.standard_id == standard.id)
            .order_by(StandardClause.order_no.asc(), StandardClause.id.asc())
            .all()
        )
        query = db.query(ReviewCheckpoint).filter(
            ReviewCheckpoint.standard_id == standard.id,
            ReviewCheckpoint.status != "archived",
        )
        if status:
            query = query.filter(ReviewCheckpoint.status == status)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    ReviewCheckpoint.rule_code.ilike(like),
                    ReviewCheckpoint.rule_text.ilike(like),
                    ReviewCheckpoint.clause_text.ilike(like),
                    cast(ReviewCheckpoint.object_terms, String).ilike(like),
                )
            )
        checkpoints = query.order_by(ReviewCheckpoint.clause_id.asc(), ReviewCheckpoint.id.asc()).all()
        return standard, clauses, checkpoints

    def get_checkpoint(self, db: Session, checkpoint_id: int) -> ReviewCheckpoint:
        row = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.id == checkpoint_id).first()
        if not row or row.status == "archived":
            raise PlatformError(f"Review checkpoint id={checkpoint_id} not found", status_code=404)
        return row

    def create_checkpoint(self, db: Session, data: ReviewCheckpointCreate) -> ReviewCheckpoint:
        self._validate_values(data.status)
        row = ReviewCheckpoint(**data.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def update_checkpoint(self, db: Session, checkpoint_id: int, data: ReviewCheckpointUpdate) -> ReviewCheckpoint:
        row = self.get_checkpoint(db, checkpoint_id)
        values = data.model_dump(exclude_unset=True)
        self._validate_values(values.get("status"))
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return row

    def archive_standard_checkpoints(self, db: Session, standard_id: int) -> int:
        count = (
            db.query(ReviewCheckpoint)
            .filter(
                ReviewCheckpoint.standard_id == standard_id,
                ReviewCheckpoint.status != "archived",
            )
            .update({"status": "archived", "updated_at": datetime.utcnow()}, synchronize_session="fetch")
        )
        db.commit()
        return count

    def delete_checkpoint(self, db: Session, checkpoint_id: int) -> ReviewCheckpoint:
        row = self.get_checkpoint(db, checkpoint_id)
        row.status = "archived"
        db.commit()
        db.refresh(row)
        return row

    def import_manual_checkpoints(self, db: Session, data: ManualCheckpointImportRequest) -> dict[str, Any]:
        clause = (
            db.query(StandardClause)
            .filter(StandardClause.id == data.clause_id, StandardClause.standard_id == data.standard_id)
            .first()
        )
        if not clause:
            raise PlatformError(
                f"Standard clause id={data.clause_id} not found in standard id={data.standard_id}",
                status_code=404,
            )

        checkpoint_payloads = _checkpoint_payloads_from_extracted(data.payload)
        if not checkpoint_payloads:
            raise PlatformError("No valid checkpoints found in JSON payload.", status_code=400)

        checkpoint_ids: list[int] = []
        now = datetime.utcnow()
        for index, payload in enumerate(checkpoint_payloads, start=1):
            checkpoint = ReviewCheckpoint(
                rule_code=payload.get("rule_code") or self._default_code(clause, index),
                rule_text=payload["rule_text"],
                object_terms=payload["object_terms"],
                standard_id=clause.standard_id,
                clause_id=clause.id,
                clause_no=clause.clause_no,
                clause_text=clause.content,
                confidence=payload["confidence"],
                status="active",
                updated_at=now,
            )
            db.add(checkpoint)
            db.flush()
            checkpoint_ids.append(checkpoint.id)

        db.commit()
        return {"created_count": len(checkpoint_ids), "checkpoint_ids": checkpoint_ids}

    def create_generation_job(
        self,
        db: Session,
        data: GenerateCheckpointsFromClausesRequest,
        *,
        created_by: int | None = None,
    ) -> ReviewCheckpointGenerationJob:
        clause_ids = _dedupe_ints(data.clause_ids)
        if not clause_ids:
            raise PlatformError("clause_ids is required.", status_code=400)

        clauses = (
            db.query(StandardClause)
            .filter(StandardClause.id.in_(clause_ids))
            .order_by(StandardClause.standard_id.asc(), StandardClause.order_no.asc(), StandardClause.id.asc())
            .all()
        )
        found_ids = {clause.id for clause in clauses}
        missing = [clause_id for clause_id in clause_ids if clause_id not in found_ids]
        standard_id = data.standard_id or (clauses[0].standard_id if clauses else None)

        job = ReviewCheckpointGenerationJob(
            standard_id=standard_id,
            clause_ids=clause_ids,
            use_llm=data.use_llm,
            concurrency=_normalize_generation_concurrency(data.concurrency),
            status="queued",
            total_clauses=len(clause_ids),
            processed_clauses=len(missing),
            failed_count=len(missing),
            failed=[{"clause_id": clause_id, "reason": "clause not found"} for clause_id in missing],
            created_by=created_by,
        )
        db.add(job)
        db.flush()

        for clause in clauses:
            db.add(
                ReviewCheckpointGenerationItem(
                    job_id=job.id,
                    standard_id=clause.standard_id,
                    clause_id=clause.id,
                    clause_no=clause.clause_no,
                    clause_title=clause.title,
                    status="queued",
                )
            )
        for clause_id in missing:
            db.add(
                ReviewCheckpointGenerationItem(
                    job_id=job.id,
                    standard_id=standard_id,
                    clause_id=clause_id,
                    status="failed",
                    message="clause not found",
                    started_at=datetime.utcnow(),
                    finished_at=datetime.utcnow(),
                )
            )

        db.commit()
        db.refresh(job)

        if clauses:
            from app.workers.review_checkpoint_tasks import generate_review_checkpoints_job

            async_result = generate_review_checkpoints_job.delay(job.id)
            job.celery_task_id = async_result.id
            db.commit()
            db.refresh(job)
        else:
            job.status = "failed"
            job.error_message = "No valid clauses found."
            job.finished_at = datetime.utcnow()
            db.commit()
            db.refresh(job)

        return job

    def list_generation_jobs(
        self,
        db: Session,
        *,
        standard_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewCheckpointGenerationJob], int]:
        query = db.query(ReviewCheckpointGenerationJob)
        if standard_id:
            query = query.filter(ReviewCheckpointGenerationJob.standard_id == standard_id)
        if status:
            query = query.filter(ReviewCheckpointGenerationJob.status == status)
        total = query.count()
        items = (
            query.order_by(ReviewCheckpointGenerationJob.created_at.desc(), ReviewCheckpointGenerationJob.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_generation_job(self, db: Session, job_id: int) -> ReviewCheckpointGenerationJob:
        row = db.query(ReviewCheckpointGenerationJob).filter(ReviewCheckpointGenerationJob.id == job_id).first()
        if not row:
            raise PlatformError(f"Checkpoint generation job id={job_id} not found", status_code=404)
        return row

    def get_generation_job_tree(
        self,
        db: Session,
        job_id: int,
    ) -> tuple[
        ReviewCheckpointGenerationJob,
        StandardDocument | None,
        list[StandardClause],
        list[ReviewCheckpointGenerationItem],
        list[ReviewCheckpoint],
    ]:
        job = self.get_generation_job(db, job_id)
        items = (
            db.query(ReviewCheckpointGenerationItem)
            .filter(ReviewCheckpointGenerationItem.job_id == job.id)
            .order_by(ReviewCheckpointGenerationItem.clause_id.asc(), ReviewCheckpointGenerationItem.id.asc())
            .all()
        )
        standard_id = job.standard_id or next((item.standard_id for item in items if item.standard_id), None)
        standard = (
            db.query(StandardDocument).filter(StandardDocument.id == standard_id).first()
            if standard_id
            else None
        )
        if standard_id:
            clauses = (
                db.query(StandardClause)
                .filter(StandardClause.standard_id == standard_id)
                .order_by(StandardClause.order_no.asc(), StandardClause.id.asc())
                .all()
            )
        else:
            clause_ids = [item.clause_id for item in items if item.clause_id]
            clauses = (
                db.query(StandardClause)
                .filter(StandardClause.id.in_(clause_ids))
                .order_by(StandardClause.order_no.asc(), StandardClause.id.asc())
                .all()
                if clause_ids
                else []
            )

        checkpoint_ids = [
            int(checkpoint_id)
            for item in items
            for checkpoint_id in (item.checkpoint_ids or [])
            if checkpoint_id
        ]
        checkpoints = (
            db.query(ReviewCheckpoint)
            .filter(ReviewCheckpoint.id.in_(checkpoint_ids))
            .order_by(ReviewCheckpoint.clause_id.asc(), ReviewCheckpoint.id.asc())
            .all()
            if checkpoint_ids
            else []
        )
        return job, standard, clauses, items, checkpoints

    def export_checkpoints_to_excel(
        self,
        db: Session,
        *,
        standard_id: int,
    ) -> tuple[io.BytesIO, str]:
        standard = db.query(StandardDocument).filter(StandardDocument.id == standard_id).first()
        if not standard or standard.status == "archived":
            raise PlatformError(f"Standard document id={standard_id} not found", status_code=404)

        checkpoints = (
            db.query(ReviewCheckpoint)
            .filter(
                ReviewCheckpoint.standard_id == standard_id,
                ReviewCheckpoint.status != "archived",
            )
            .order_by(ReviewCheckpoint.clause_id.asc(), ReviewCheckpoint.id.asc())
            .all()
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Checkpoints"

        ws.append(["序号", "clause_no", "rule_code", "rule_text", "confidence"])
        for idx, cp in enumerate(checkpoints, start=1):
            ws.append([
                idx,
                _sanitize_cell(cp.clause_no or ""),
                _sanitize_cell(cp.rule_code or ""),
                _sanitize_cell(cp.rule_text or ""),
                cp.confidence if cp.confidence is not None else "",
            ])

        safe_name = re.sub(r"[^\w一-鿿\-]", "_", standard.standard_name).strip("_")
        filename = f"{safe_name}_checkpoints.xlsx"

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer, filename

    def list_generation_items(
        self,
        db: Session,
        *,
        job_id: int | None = None,
        standard_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewCheckpointGenerationItem], int]:
        query = db.query(ReviewCheckpointGenerationItem)
        if job_id:
            query = query.filter(ReviewCheckpointGenerationItem.job_id == job_id)
        if standard_id:
            query = query.filter(ReviewCheckpointGenerationItem.standard_id == standard_id)
        if status:
            query = query.filter(ReviewCheckpointGenerationItem.status == status)
        total = query.count()
        items = (
            query.order_by(ReviewCheckpointGenerationItem.created_at.desc(), ReviewCheckpointGenerationItem.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    async def run_generation_job(self, db: Session, job_id: int) -> dict[str, Any]:
        job = self.get_generation_job(db, job_id)
        if job.status not in {"queued", "failed"}:
            return {"job_id": job.id, "status": job.status, "message": "job already started"}

        concurrency = _normalize_generation_concurrency(getattr(job, "concurrency", None))
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.error_message = None
        db.commit()
        job_id_value = job.id
        use_llm = job.use_llm

        items = (
            db.query(ReviewCheckpointGenerationItem)
            .filter(ReviewCheckpointGenerationItem.job_id == job_id_value)
            .filter(ReviewCheckpointGenerationItem.status == "queued")
            .order_by(ReviewCheckpointGenerationItem.id.asc())
            .all()
        )

        try:
            semaphore = asyncio.Semaphore(concurrency)

            async def run_item(item_id: int, serial_offset: int) -> None:
                async with semaphore:
                    await self._run_generation_job_item(
                        job_id=job_id_value,
                        item_id=item_id,
                        use_llm=use_llm,
                        serial_offset=serial_offset,
                    )

            await asyncio.gather(
                *(run_item(item.id, index) for index, item in enumerate(items, start=1)),
            )
        except Exception as exc:
            job = self.get_generation_job(db, job_id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            db.commit()
            raise

        db.expire_all()
        self._refresh_generation_job_summary(db, job_id_value, finalize=True)
        job = self.get_generation_job(db, job_id_value)
        return {"job_id": job.id, "status": job.status, "created_count": job.created_count}

    async def _run_generation_job_item(
        self,
        *,
        job_id: int,
        item_id: int,
        use_llm: bool,
        serial_offset: int,
    ) -> None:
        db = SessionLocal()
        try:
            item = db.query(ReviewCheckpointGenerationItem).filter(ReviewCheckpointGenerationItem.id == item_id).first()
            if not item or item.status != "queued":
                return

            item.status = "running"
            item.started_at = datetime.utcnow()
            db.commit()

            clause = db.query(StandardClause).filter(StandardClause.id == item.clause_id).first()
            if not clause:
                item.status = "failed"
                item.message = "clause not found"
                item.finished_at = datetime.utcnow()
                db.commit()
                self._refresh_generation_job_summary(db, job_id)
                return

            standard = db.query(StandardDocument).filter(StandardDocument.id == clause.standard_id).first()
            try:
                checkpoint_ids, skipped_reason = await self._create_checkpoints_for_clause(
                    db,
                    standard,
                    clause,
                    use_llm=use_llm,
                    job_id=job_id,
                    serial_offset=serial_offset,
                )
                item.checkpoint_ids = checkpoint_ids
                item.created_count = len(checkpoint_ids)
                item.status = "skipped" if skipped_reason else "success"
                item.message = skipped_reason or f"created {len(checkpoint_ids)} checkpoint(s)"
                item.finished_at = datetime.utcnow()
                db.commit()
            except Exception as exc:
                db.rollback()
                item = db.query(ReviewCheckpointGenerationItem).filter(ReviewCheckpointGenerationItem.id == item_id).first()
                if item:
                    item.status = "failed"
                    item.message = str(exc)
                    item.finished_at = datetime.utcnow()
                    db.commit()
            self._refresh_generation_job_summary(db, job_id)
        finally:
            db.close()

    async def generate_from_standard_clauses(
        self,
        db: Session,
        data: GenerateCheckpointsFromClausesRequest,
    ) -> dict[str, Any]:
        clauses = (
            db.query(StandardClause)
            .filter(StandardClause.id.in_(data.clause_ids))
            .order_by(StandardClause.standard_id.asc(), StandardClause.order_no.asc(), StandardClause.id.asc())
            .all()
        )
        found_ids = {clause.id for clause in clauses}
        failed = [
            {"clause_id": clause_id, "reason": "clause not found"}
            for clause_id in data.clause_ids
            if clause_id not in found_ids
        ]
        skipped: list[dict[str, Any]] = []
        checkpoint_ids: list[int] = []

        for clause in clauses:
            standard = db.query(StandardDocument).filter(StandardDocument.id == clause.standard_id).first()
            try:
                ids, skipped_reason = await self._create_checkpoints_for_clause(
                    db,
                    standard,
                    clause,
                    use_llm=data.use_llm,
                    serial_offset=len(checkpoint_ids) + 1,
                )
                if skipped_reason:
                    skipped.append({"clause_id": clause.id, "reason": skipped_reason})
                    db.commit()
                    continue
                checkpoint_ids.extend(ids)
            except Exception as exc:
                db.rollback()
                failed.append({"clause_id": clause.id, "reason": str(exc)})
            else:
                db.commit()

        return {
            "created_count": len(checkpoint_ids),
            "checkpoint_ids": checkpoint_ids,
            "failed": failed,
            "skipped": skipped,
        }

    async def _create_checkpoints_for_clause(
        self,
        db: Session,
        standard: StandardDocument | None,
        clause: StandardClause,
        *,
        use_llm: bool,
        job_id: int | None = None,
        serial_offset: int = 1,
    ) -> tuple[list[int], str | None]:
        extracted = await self._extract_checkpoints(standard, clause, use_llm=use_llm, job_id=job_id)
        checkpoint_payloads = _checkpoint_payloads_from_extracted(extracted)
        if not checkpoint_payloads:
            self._archive_clause_checkpoints(db, clause)
            return [], "no checkpoint generated"

        existing_rows = (
            db.query(ReviewCheckpoint)
            .filter(
                ReviewCheckpoint.standard_id == clause.standard_id,
                ReviewCheckpoint.clause_id == clause.id,
                ReviewCheckpoint.status != "archived",
            )
            .order_by(ReviewCheckpoint.id.asc())
            .all()
        )
        existing_by_text = {row.rule_text: row for row in existing_rows}
        checkpoint_ids: list[int] = []
        used_ids: set[int] = set()
        now = datetime.utcnow()
        for index, payload in enumerate(checkpoint_payloads, start=1):
            rule_text = payload["rule_text"]
            checkpoint = existing_by_text.get(rule_text)
            values = {
                "rule_code": payload.get("rule_code") or self._default_code(clause, index),
                "rule_text": rule_text,
                "object_terms": payload["object_terms"],
                "standard_id": clause.standard_id,
                "clause_id": clause.id,
                "clause_no": clause.clause_no,
                "clause_text": clause.content,
                "confidence": payload["confidence"],
                "status": "active",
                "updated_at": now,
            }
            if checkpoint:
                for key, value in values.items():
                    setattr(checkpoint, key, value)
            else:
                checkpoint = ReviewCheckpoint(**values)
                db.add(checkpoint)
            db.flush()
            checkpoint_ids.append(checkpoint.id)
            used_ids.add(checkpoint.id)
        for checkpoint in existing_rows:
            if checkpoint.id not in used_ids and checkpoint.status == "active":
                checkpoint.status = "archived"
                checkpoint.updated_at = now
        db.flush()
        return checkpoint_ids, None

    def _archive_clause_checkpoints(self, db: Session, clause: StandardClause) -> None:
        (
            db.query(ReviewCheckpoint)
            .filter(
                ReviewCheckpoint.standard_id == clause.standard_id,
                ReviewCheckpoint.clause_id == clause.id,
                ReviewCheckpoint.status == "active",
            )
            .update({"status": "archived", "updated_at": datetime.utcnow()}, synchronize_session=False)
        )

    def _refresh_generation_job_summary(self, db: Session, job_id: int, *, finalize: bool = False) -> None:
        db.expire_all()
        job = self.get_generation_job(db, job_id)
        items = db.query(ReviewCheckpointGenerationItem).filter(ReviewCheckpointGenerationItem.job_id == job.id).all()
        created_ids: list[int] = []
        failed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        processed = 0
        for item in items:
            if item.status in {"success", "skipped", "failed"}:
                processed += 1
            if item.checkpoint_ids:
                created_ids.extend(int(checkpoint_id) for checkpoint_id in item.checkpoint_ids)
            if item.status == "failed":
                failed.append({"clause_id": item.clause_id, "clause_no": item.clause_no, "reason": item.message or "failed"})
            if item.status == "skipped":
                skipped.append({"clause_id": item.clause_id, "clause_no": item.clause_no, "reason": item.message or "skipped"})

        job.processed_clauses = processed
        job.created_count = len(created_ids)
        job.failed_count = len(failed)
        job.skipped_count = len(skipped)
        job.checkpoint_ids = created_ids
        job.failed = failed
        job.skipped = skipped
        if finalize or processed >= job.total_clauses:
            job.finished_at = datetime.utcnow()
            if job.created_count > 0 and job.failed_count == 0:
                job.status = "success"
                job.error_message = None
            elif job.created_count > 0:
                job.status = "partial_success"
                job.error_message = None
            else:
                job.status = "failed"
                job.error_message = "No checkpoint generated."
        else:
            job.status = "running"
        db.commit()

    async def _extract_checkpoints(
        self,
        standard: StandardDocument | None,
        clause: StandardClause,
        *,
        use_llm: bool,
        job_id: int | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        if not use_llm:
            return {"checkpoints": self._heuristic_checkpoints(clause)}

        model_service = ModelService()
        clause_title = clause.title or ""
        clause_content = (clause.content or "").strip()
        if clause_content == clause_title:
            clause_title = ""
        prompt = (
            CHECKPOINT_PROMPT.replace("{standard_name}", standard.standard_name if standard else "")
            .replace("{clause_no}", clause.clause_no or "")
            .replace("{clause_title}", clause_title)
            .replace("{clause_content}", clause_content)
        )
        payload = {
            "model": model_service.default_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1800,
        }
        metadata = {
            "operation": "checkpoint_generation.extract",
            "job_id": job_id,
            "standard_id": clause.standard_id,
            "standard_name": standard.standard_name if standard else None,
            "clause_id": clause.id,
            "clause_no": clause.clause_no,
            "clause_title": clause.title,
            "clause_chars": len(clause.content or ""),
            "prompt_clause_chars": len(clause_content),
            "use_llm": use_llm,
        }
        with langfuse_observation(
            name="checkpoint_generation.extract",
            input_data={"messages": payload["messages"]},
            metadata=metadata,
            session_id=(
                f"checkpoint-generation-job:{job_id}"
                if job_id
                else f"checkpoint-generation-standard:{clause.standard_id}"
            ),
            tags=["checkpoint_generation", "llm"],
            as_type="generation",
            model=model_service.default_model,
        ) as observation:
            result = await model_service.call_model(payload)
            content = ((result.get("output") or {}).get("content") or "").strip()
            parsed = _parse_json(content)
            checkpoint_payloads = parsed if isinstance(parsed, list) else parsed.get("checkpoints", [])
            update_langfuse_observation(
                observation,
                output={"content": content},
                metadata=metadata
                | {
                    "output_chars": len(content),
                    "generated_checkpoint_count": (
                        len(checkpoint_payloads) if isinstance(checkpoint_payloads, list) else 0
                    ),
                },
            )
        return parsed

    def _heuristic_checkpoints(self, clause: StandardClause) -> list[dict[str, Any]]:
        content = clause.content or ""
        title = clause.title or clause.clause_no or "规范条文"
        objects = _extract_objects(content + title)
        if any(term in content for term in ("严禁", "不得", "禁止", "不应", "应", "应当", "必须")):
            return [
                {
                    "rule_text": content[:500],
                    "object_terms": objects,
                    "confidence": 0.5,
                }
            ]
        return []

    def _default_code(self, clause: StandardClause, serial: int) -> str:
        raw = clause.clause_no or f"CLAUSE-{clause.id}"
        safe = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").upper()
        return f"CP-{safe}-{serial:03d}"

    def _default_name(self, clause: StandardClause) -> str:
        return f"{clause.clause_no or clause.id} {clause.title or '规范审查点'}"

    def _validate_values(self, status: str | None) -> None:
        if status and status not in CHECKPOINT_STATUSES:
            raise PlatformError(f"Invalid checkpoint status: {status}", status_code=400)


def _normalize_generation_concurrency(value: int | None) -> int:
    if value is None:
        return DEFAULT_GENERATION_CONCURRENCY
    return max(1, min(int(value), MAX_GENERATION_CONCURRENCY))


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]


def _as_confidence(value: Any, *, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _checkpoint_payloads_from_extracted(extracted: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(extracted, list):
        raw_checkpoints = extracted
    elif "checkpoints" in extracted:
        raw_checkpoints = extracted.get("checkpoints", [])
    elif "rule_text" in extracted:
        raw_checkpoints = [extracted]
    else:
        raw_checkpoints = []
    if not isinstance(raw_checkpoints, list):
        return []

    checkpoints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_checkpoint in raw_checkpoints:
        if not isinstance(raw_checkpoint, dict):
            continue
        rule_text = _as_string(raw_checkpoint.get("rule_text"))
        if not rule_text or rule_text in seen:
            continue
        seen.add(rule_text)
        checkpoints.append(
            {
                "rule_code": _as_string(raw_checkpoint.get("rule_code")) or None,
                "rule_text": rule_text,
                "object_terms": _as_list(raw_checkpoint.get("object_terms")),
                "confidence": _as_confidence(raw_checkpoint.get("confidence"), default=0.0),
            }
        )
    return checkpoints


def _as_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _dedupe_ints(values: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        int_value = int(value)
        if int_value not in seen:
            seen.add(int_value)
            result.append(int_value)
    return result


def _sanitize_cell(value: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)


def _parse_json(content: str) -> dict[str, Any] | list[dict[str, Any]]:
    if not content:
        raise PlatformError("LLM returned empty content.", status_code=502)
    cleaned = _strip_json_fence(content)
    last_error: json.JSONDecodeError | None = None
    for candidate in _json_candidates(cleaned):
        for variant in _json_candidate_variants(candidate):
            try:
                parsed = json.loads(variant, strict=False)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
            if not isinstance(parsed, (dict, list)):
                raise PlatformError("LLM output JSON must be an object or array.", status_code=502)
            return parsed
    if last_error:
        raise PlatformError(f"LLM output is not valid JSON: {last_error}", status_code=502)
    raise PlatformError("LLM output is not JSON.", status_code=502)


def _strip_json_fence(content: str) -> str:
    cleaned = content.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return fence_match.group(1).strip() if fence_match else cleaned


def _json_candidate_variants(candidate: str) -> list[str]:
    repaired = _repair_invalid_json_escapes(candidate)
    compacted = re.sub(r",(\s*[}\]])", r"\1", repaired)
    variants = [candidate, repaired, compacted]
    return list(dict.fromkeys(variants))


def _repair_invalid_json_escapes(candidate: str) -> str:
    candidate = re.sub(r"\\u(?![0-9a-fA-F]{4})", r"\\\\u", candidate)
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", candidate)


def _json_candidates(content: str) -> list[str]:
    candidates: list[str] = []
    for start, char in enumerate(content):
        if char not in "{[":
            continue
        candidate = _balanced_json_candidate(content, start)
        if candidate:
            candidates.append(candidate)
    return candidates


def _balanced_json_candidate(content: str, start: int) -> str | None:
    stack: list[str] = []
    in_string = False
    escaped = False
    for index in range(start, len(content)):
        char = content[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char in "{[":
            stack.append("}" if char == "{" else "]")
            continue
        if char in "}]":
            if not stack or stack.pop() != char:
                return None
            if not stack:
                return content[start : index + 1].strip()
    return None


def _extract_objects(text: str) -> list[str]:
    candidates = ("盘扣架", "架体", "支撑架", "基础", "基础构造", "剪刀撑", "立杆", "水平杆", "混凝土浇筑", "拆除")
    return [item for item in candidates if item in text]




def get_review_checkpoint_service() -> Generator[ReviewCheckpointService, None, None]:
    yield ReviewCheckpointService()
