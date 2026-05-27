from __future__ import annotations

import json
import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.db.models import (
    ReviewCheckpoint,
    ReviewCheckpointGenerationItem,
    ReviewCheckpointGenerationJob,
    StandardClause,
    StandardDocument,
)
from app.review_checkpoints.schemas import (
    GenerateCheckpointsFromClausesRequest,
    ReviewCheckpointCreate,
    ReviewCheckpointUpdate,
)
from app.services.model_service import ModelService
from app.utils.exceptions import PlatformError
from app.utils.langfuse import langfuse_observation, update_langfuse_observation


CHECKPOINT_TYPES = {
    "required_content",
    "parameter_threshold",
    "forbidden_content",
    "procedure_required",
    "semantic_check",
    "cross_section_consistency",
}
CHECKPOINT_STATUSES = {"draft", "active", "disabled", "archived"}
GENERATION_JOB_STATUSES = {"queued", "running", "success", "partial_success", "failed"}

CHECKPOINT_PROMPT = """你是一名施工规范审查点抽取助手。
任务：将规范条文转换为施工方案审查点。一个条文可以生成多个审查点。

要求：
1. 只能基于条文原文生成，不得编造。
2. 审查点用于后续与施工方案章节画像匹配，不直接生成 ReviewIssue。
3. 每个审查点必须包含 chapter_types、target_objects、target_parameters、check_goal、check_method。
4. 如果条文无法形成明确审查点，输出空数组。
5. 只输出 JSON，不要输出 Markdown。

规范名称：{standard_name}
条文编号：{clause_no}
条文原文：{clause_content}

输出格式：
{{
  "checkpoints": [
    {{
      "checkpoint_name": "",
      "checkpoint_type": "required_content",
      "domain": "",
      "subdomain": "",
      "work_type": "",
      "chapter_types": [],
      "target_objects": [],
      "target_parameters": [],
      "keywords": [],
      "check_goal": "",
      "check_method": "",
      "expected_items": [],
      "forbidden_items": [],
      "parameters": {{}},
      "applicable_condition": {{}},
      "risk_level": "major",
      "is_mandatory": false,
      "priority": 0
    }}
  ]
}}

checkpoint_type 只能从以下值中选择：
- required_content
- parameter_threshold
- forbidden_content
- procedure_required
- semantic_check
- cross_section_consistency
"""


class ReviewCheckpointService:
    def list_checkpoints(
        self,
        db: Session,
        *,
        status: str | None = None,
        checkpoint_type: str | None = None,
        domain: str | None = None,
        work_type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewCheckpoint], int]:
        query = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.status != "archived")
        if status:
            query = query.filter(ReviewCheckpoint.status == status)
        if checkpoint_type:
            query = query.filter(ReviewCheckpoint.checkpoint_type == checkpoint_type)
        if domain:
            query = query.filter(ReviewCheckpoint.domain == domain)
        if work_type:
            query = query.filter(or_(ReviewCheckpoint.work_type == work_type, ReviewCheckpoint.work_type.is_(None), ReviewCheckpoint.work_type == ""))
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    ReviewCheckpoint.checkpoint_name.ilike(like),
                    ReviewCheckpoint.check_goal.ilike(like),
                    ReviewCheckpoint.clause_text.ilike(like),
                    cast(ReviewCheckpoint.keywords, String).ilike(like),
                )
            )
        total = query.count()
        items = (
            query.order_by(ReviewCheckpoint.priority.desc(), ReviewCheckpoint.created_at.desc(), ReviewCheckpoint.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_checkpoint(self, db: Session, checkpoint_id: int) -> ReviewCheckpoint:
        row = db.query(ReviewCheckpoint).filter(ReviewCheckpoint.id == checkpoint_id).first()
        if not row or row.status == "archived":
            raise PlatformError(f"Review checkpoint id={checkpoint_id} not found", status_code=404)
        return row

    def create_checkpoint(self, db: Session, data: ReviewCheckpointCreate) -> ReviewCheckpoint:
        self._validate_values(data.checkpoint_type, data.status)
        row = ReviewCheckpoint(**data.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def update_checkpoint(self, db: Session, checkpoint_id: int, data: ReviewCheckpointUpdate) -> ReviewCheckpoint:
        row = self.get_checkpoint(db, checkpoint_id)
        values = data.model_dump(exclude_unset=True)
        self._validate_values(values.get("checkpoint_type"), values.get("status"))
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return row

    def delete_checkpoint(self, db: Session, checkpoint_id: int) -> ReviewCheckpoint:
        row = self.get_checkpoint(db, checkpoint_id)
        row.status = "archived"
        db.commit()
        db.refresh(row)
        return row

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

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.error_message = None
        db.commit()

        items = (
            db.query(ReviewCheckpointGenerationItem)
            .filter(ReviewCheckpointGenerationItem.job_id == job.id)
            .filter(ReviewCheckpointGenerationItem.status == "queued")
            .order_by(ReviewCheckpointGenerationItem.id.asc())
            .all()
        )

        try:
            for item in items:
                item.status = "running"
                item.started_at = datetime.utcnow()
                db.commit()

                clause = db.query(StandardClause).filter(StandardClause.id == item.clause_id).first()
                if not clause:
                    item.status = "failed"
                    item.message = "clause not found"
                    item.finished_at = datetime.utcnow()
                    self._refresh_generation_job_summary(db, job.id)
                    continue

                standard = db.query(StandardDocument).filter(StandardDocument.id == clause.standard_id).first()
                try:
                    checkpoint_ids, skipped_reason = await self._create_checkpoints_for_clause(
                        db,
                        standard,
                        clause,
                        use_llm=job.use_llm,
                        job_id=job.id,
                        serial_offset=job.created_count + 1,
                    )
                    item.checkpoint_ids = checkpoint_ids
                    item.created_count = len(checkpoint_ids)
                    item.status = "skipped" if skipped_reason else "success"
                    item.message = skipped_reason or f"created {len(checkpoint_ids)} checkpoint(s)"
                    item.finished_at = datetime.utcnow()
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    item = db.query(ReviewCheckpointGenerationItem).filter(ReviewCheckpointGenerationItem.id == item.id).first()
                    if item:
                        item.status = "failed"
                        item.message = str(exc)
                        item.finished_at = datetime.utcnow()
                        db.commit()
                self._refresh_generation_job_summary(db, job.id)
        except Exception as exc:
            job = self.get_generation_job(db, job_id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            db.commit()
            raise

        self._refresh_generation_job_summary(db, job.id, finalize=True)
        job = self.get_generation_job(db, job.id)
        return {"job_id": job.id, "status": job.status, "created_count": job.created_count}

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
        checkpoint_payloads = extracted if isinstance(extracted, list) else extracted.get("checkpoints", [])
        if not checkpoint_payloads:
            return [], "no checkpoint generated"

        checkpoint_ids: list[int] = []
        for index, payload in enumerate(checkpoint_payloads, start=serial_offset):
            checkpoint_type = payload.get("checkpoint_type") or "semantic_check"
            if checkpoint_type not in CHECKPOINT_TYPES:
                checkpoint_type = "semantic_check"
            checkpoint = ReviewCheckpoint(
                checkpoint_code=payload.get("checkpoint_code") or self._default_code(clause, index),
                checkpoint_name=(payload.get("checkpoint_name") or self._default_name(clause))[:255],
                checkpoint_type=checkpoint_type,
                domain=payload.get("domain") or None,
                subdomain=payload.get("subdomain") or None,
                work_type=payload.get("work_type") or None,
                standard_id=clause.standard_id,
                clause_id=clause.id,
                clause_no=clause.clause_no,
                clause_text=clause.content,
                chapter_types=_as_list(payload.get("chapter_types")),
                target_objects=_as_list(payload.get("target_objects")),
                target_parameters=_as_list(payload.get("target_parameters")),
                keywords=_as_list(payload.get("keywords")),
                check_goal=payload.get("check_goal") or clause.content[:300],
                check_method=payload.get("check_method") or checkpoint_type,
                expected_items=_as_list(payload.get("expected_items")),
                forbidden_items=_as_list(payload.get("forbidden_items")),
                parameters=_as_dict(payload.get("parameters")),
                applicable_condition=_as_dict(payload.get("applicable_condition")),
                risk_level=payload.get("risk_level") or ("critical" if clause.is_mandatory else "major"),
                is_mandatory=bool(payload.get("is_mandatory", clause.is_mandatory)),
                priority=int(payload.get("priority") or (100 if clause.is_mandatory else 0)),
                status="active",
            )
            db.add(checkpoint)
            db.flush()
            checkpoint_ids.append(checkpoint.id)
        return checkpoint_ids, None

    def _refresh_generation_job_summary(self, db: Session, job_id: int, *, finalize: bool = False) -> None:
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
            elif job.created_count > 0:
                job.status = "partial_success"
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
        prompt = CHECKPOINT_PROMPT.format(
            standard_name=standard.standard_name if standard else "",
            clause_no=clause.clause_no or "",
            clause_content=clause.content or "",
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
        parameters = _extract_parameter_names(content)
        chapter_types = ["construction_technology"] if any(term in content + title for term in ("施工", "搭设", "拆除", "浇筑", "构造")) else []
        if any(term in content for term in ("严禁", "不得", "禁止")):
            return [
                {
                    "checkpoint_name": f"{title} 禁止性内容审查",
                    "checkpoint_type": "forbidden_content",
                    "chapter_types": chapter_types,
                    "target_objects": objects,
                    "target_parameters": parameters,
                    "keywords": _keywords_from_text(content),
                    "check_goal": "检查施工方案是否存在规范禁止的做法。",
                    "check_method": "keyword",
                    "forbidden_items": [term for term in ("严禁", "不得", "禁止") if term in content],
                    "risk_level": "critical" if clause.is_mandatory else "major",
                    "is_mandatory": clause.is_mandatory,
                }
            ]
        if _extract_threshold(content):
            return [
                {
                    "checkpoint_name": f"{title} 参数阈值审查",
                    "checkpoint_type": "parameter_threshold",
                    "chapter_types": chapter_types,
                    "target_objects": objects,
                    "target_parameters": parameters,
                    "keywords": _keywords_from_text(content),
                    "check_goal": "检查施工方案中的参数是否满足规范阈值。",
                    "check_method": "parameter_threshold",
                    "parameters": _extract_threshold(content),
                    "risk_level": "major",
                    "is_mandatory": clause.is_mandatory,
                }
            ]
        if any(term in content for term in ("应", "应当", "必须")):
            return [
                {
                    "checkpoint_name": f"{title} 必要内容审查",
                    "checkpoint_type": "required_content",
                    "chapter_types": chapter_types,
                    "target_objects": objects,
                    "target_parameters": parameters,
                    "keywords": _keywords_from_text(content),
                    "check_goal": "检查施工方案是否覆盖条文要求的关键内容。",
                    "check_method": "keyword",
                    "expected_items": _keywords_from_text(content)[:5],
                    "risk_level": "critical" if clause.is_mandatory else "major",
                    "is_mandatory": clause.is_mandatory,
                }
            ]
        return []

    def _default_code(self, clause: StandardClause, serial: int) -> str:
        raw = clause.clause_no or f"CLAUSE-{clause.id}"
        safe = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").upper()
        return f"CP-{safe}-{serial:03d}"

    def _default_name(self, clause: StandardClause) -> str:
        return f"{clause.clause_no or clause.id} {clause.title or '规范审查点'}"

    def _validate_values(self, checkpoint_type: str | None, status: str | None) -> None:
        if checkpoint_type and checkpoint_type not in CHECKPOINT_TYPES:
            raise PlatformError(f"Invalid checkpoint_type: {checkpoint_type}", status_code=400)
        if status and status not in CHECKPOINT_STATUSES:
            raise PlatformError(f"Invalid checkpoint status: {status}", status_code=400)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _dedupe_ints(values: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        int_value = int(value)
        if int_value not in seen:
            seen.add(int_value)
            result.append(int_value)
    return result


def _parse_json(content: str) -> dict[str, Any] | list[dict[str, Any]]:
    if not content:
        raise PlatformError("LLM returned empty content.", status_code=502)
    cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
        if not match:
            raise PlatformError("LLM output is not JSON.", status_code=502)
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, (dict, list)):
        raise PlatformError("LLM output JSON must be an object or array.", status_code=502)
    return parsed


def _extract_objects(text: str) -> list[str]:
    candidates = ("盘扣架", "架体", "支撑架", "基础", "基础构造", "剪刀撑", "立杆", "水平杆", "混凝土浇筑", "拆除")
    return [item for item in candidates if item in text]


def _extract_parameter_names(text: str) -> list[str]:
    candidates = ("立杆间距", "步距", "架体高度", "自由端高度", "承载力", "搭接长度", "浇筑速度", "分层厚度")
    return [item for item in candidates if item in text]


def _keywords_from_text(text: str) -> list[str]:
    candidates = (
        "盘扣",
        "架体",
        "基础",
        "剪刀撑",
        "立杆",
        "水平杆",
        "扫地杆",
        "拆除",
        "浇筑",
        "验收",
        "承载力",
        "安全",
    )
    return [item for item in candidates if item in text]


def _extract_threshold(text: str) -> dict[str, Any]:
    match = re.search(r"(?:不应|不得|应|必须)?\s*(?P<operator><=|>=|<|>|不小于|不大于|大于|小于|不少于|不超过)?\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mm|毫米|m|米)", text)
    if not match:
        return {}
    operator_map = {"不小于": ">=", "不少于": ">=", "大于": ">", "不大于": "<=", "不超过": "<=", "小于": "<"}
    operator = operator_map.get(match.group("operator") or "", match.group("operator") or "<=")
    return {
        "operator": operator,
        "threshold_value": match.group("value"),
        "unit": match.group("unit"),
    }


def get_review_checkpoint_service() -> Generator[ReviewCheckpointService, None, None]:
    yield ReviewCheckpointService()
