from __future__ import annotations

import json
import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    PlanDocument,
    PlanParseResult,
    PlanSection,
    StandardClause,
    StandardDocument,
    TocMatchItem,
    TocMatchJob,
)
from app.parsers.section_parse_strategies import DEFAULT_SECTION_PARSE_MODE, resolve_section_parse_mode
from app.services.model_service import ModelService
from app.utils.exceptions import PlatformError
from app.utils.langfuse import langfuse_observation, update_langfuse_observation


TOC_MATCH_PROMPT = """你是一名施工方案目录与规范目录匹配助手。

任务：只根据两个目录的一、二级标题进行语义理解，判断“规范的某一章节应该审查施工方案的哪一章节”。
不要使用或臆造正文内容。允许规范一级章节匹配施工方案二级章节，也允许一级对一级、二级对二级。

输出要求：
1. 只输出单行 JSON，不要 Markdown，不要解释文字。
2. matches 必须是数组。
3. 每条匹配必须使用输入目录中的 id。
4. 一个规范章节可以匹配多个施工方案章节；不能确定则不要输出。
5. match_type 可选值：level1_to_level1、level1_to_level2、level2_to_level1、level2_to_level2、semantic。
6. confidence 为 0-1 小数。
7. reason 不超过 30 个汉字。

输出格式：
{"matches":[{"standard_clause_id":1,"plan_section_id":2,"confidence":0.85,"reason":"简短中文理由"}]}

施工方案目录（一二级）：
{plan_toc}

规范目录（一二级）：
{standard_toc}
"""


class TocMatcherService:
    async def create_match_job(
        self,
        db: Session,
        *,
        plan_document_id: int,
        standard_id: int,
        section_parse_mode: str | None = None,
        model: str | None = None,
        created_by: int | None = None,
    ) -> TocMatchJob:
        document = self._get_plan_document(db, plan_document_id)
        standard = self._get_standard(db, standard_id)
        parse_result = self._get_parse_result(db, document, section_parse_mode)
        plan_sections = self._get_plan_toc_sections(db, document.id, parse_result.id)
        standard_clauses = self._get_standard_toc_clauses(db, standard.id)
        if not plan_sections:
            raise PlatformError("The construction plan has no parsed level-1/2 sections.", status_code=400)
        if not standard_clauses:
            raise PlatformError("The standard has no level-1/2 clauses.", status_code=400)

        job = TocMatchJob(
            plan_document_id=document.id,
            plan_parse_result_id=parse_result.id,
            standard_id=standard.id,
            model=model,
            status="running",
            created_by=created_by,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        try:
            response = await self._call_llm(plan_sections, standard_clauses, model=model, job=job)
            job.raw_llm_response = response
            matches = _extract_matches(response)
            self._persist_matches(db, job, matches, plan_sections, standard_clauses)
            job.status = "success"
            job.error_message = None
            job.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
            return job
        except Exception as exc:
            db.rollback()
            failed = db.query(TocMatchJob).filter(TocMatchJob.id == job.id).first()
            if failed:
                failed.status = "failed"
                failed.error_message = str(exc)
                if "response" in locals():
                    failed.raw_llm_response = response
                failed.completed_at = datetime.utcnow()
                db.commit()
                db.refresh(failed)
                return failed
            raise

    def list_jobs(
        self,
        db: Session,
        *,
        plan_document_id: int | None = None,
        standard_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TocMatchJob], int]:
        query = db.query(TocMatchJob)
        if plan_document_id is not None:
            query = query.filter(TocMatchJob.plan_document_id == plan_document_id)
        if standard_id is not None:
            query = query.filter(TocMatchJob.standard_id == standard_id)
        if status:
            query = query.filter(TocMatchJob.status == status)
        total = query.count()
        items = (
            query.order_by(TocMatchJob.created_at.desc(), TocMatchJob.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_job_detail(self, db: Session, job_id: int) -> tuple[TocMatchJob, list[TocMatchItem]]:
        job = db.query(TocMatchJob).filter(TocMatchJob.id == job_id).first()
        if not job:
            raise PlatformError(f"TOC match job id={job_id} not found", status_code=404)
        items = (
            db.query(TocMatchItem)
            .options(joinedload(TocMatchItem.standard_clause), joinedload(TocMatchItem.plan_section))
            .filter(TocMatchItem.job_id == job.id)
            .order_by(TocMatchItem.id.asc())
            .all()
        )
        return job, items

    def _get_plan_document(self, db: Session, document_id: int) -> PlanDocument:
        document = db.query(PlanDocument).filter(PlanDocument.id == document_id).first()
        if not document or document.document_type != "construction_plan":
            raise PlatformError(f"Construction plan document id={document_id} not found", status_code=404)
        return document

    def _get_standard(self, db: Session, standard_id: int) -> StandardDocument:
        standard = db.query(StandardDocument).filter(StandardDocument.id == standard_id).first()
        if not standard or standard.status == "archived":
            raise PlatformError(f"Standard document id={standard_id} not found", status_code=404)
        return standard

    def _get_parse_result(self, db: Session, document: PlanDocument, section_parse_mode: str | None) -> PlanParseResult:
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
            raise PlatformError(f"The construction plan has no parsed result for section_parse_mode={mode}.", status_code=400)
        return result

    def _get_plan_toc_sections(self, db: Session, document_id: int, parse_result_id: int) -> list[PlanSection]:
        return (
            db.query(PlanSection)
            .filter(
                PlanSection.document_id == document_id,
                PlanSection.parse_result_id == parse_result_id,
                PlanSection.level <= 2,
            )
            .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
            .all()
        )

    def _get_standard_toc_clauses(self, db: Session, standard_id: int) -> list[StandardClause]:
        return (
            db.query(StandardClause)
            .filter(StandardClause.standard_id == standard_id, StandardClause.level <= 2)
            .order_by(StandardClause.order_no.asc(), StandardClause.id.asc())
            .all()
        )

    async def _call_llm(
        self,
        plan_sections: list[PlanSection],
        standard_clauses: list[StandardClause],
        *,
        model: str | None = None,
        job: TocMatchJob | None = None,
    ) -> dict[str, Any]:
        prompt = TOC_MATCH_PROMPT.replace("{plan_toc}", json.dumps(_plan_toc_payload(plan_sections), ensure_ascii=False))
        prompt = prompt.replace("{standard_toc}", json.dumps(_standard_toc_payload(standard_clauses), ensure_ascii=False))
        service = ModelService()
        model_name = model or service.default_model
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 8000,
        }
        metadata = {
            "operation": "toc_matching.match",
            "job_id": job.id if job else None,
            "plan_document_id": job.plan_document_id if job else None,
            "plan_parse_result_id": job.plan_parse_result_id if job else None,
            "standard_id": job.standard_id if job else None,
            "plan_toc_count": len(plan_sections),
            "standard_toc_count": len(standard_clauses),
            "prompt_chars": len(prompt),
        }
        with langfuse_observation(
            name="toc_matching.match",
            input_data={"messages": payload["messages"]},
            metadata=metadata,
            session_id=f"toc-match-job:{job.id}" if job else None,
            tags=["toc_matching", "llm"],
            as_type="generation",
            model=model_name,
        ) as observation:
            response = await service.call_model(payload)
            content = ((response.get("output") or {}).get("content") or "").strip()
            parsed, parse_error = _loads_json_object(content)
            result_payload: dict[str, Any] = {"model_response": response, "content": content, "parsed": parsed}
            if parse_error:
                result_payload["parse_error"] = parse_error
            matches = _extract_matches(result_payload)
            update_langfuse_observation(
                observation,
                output={"content": content},
                metadata=metadata
                | {
                    "provider": response.get("provider"),
                    "model": response.get("model"),
                    "output_chars": len(content),
                    "parse_error": parse_error,
                    "recovered_match_count": len(matches),
                },
            )
        return result_payload

    def _persist_matches(
        self,
        db: Session,
        job: TocMatchJob,
        matches: list[dict[str, Any]],
        plan_sections: list[PlanSection],
        standard_clauses: list[StandardClause],
    ) -> None:
        plan_by_id = {section.id: section for section in plan_sections}
        clause_by_id = {clause.id: clause for clause in standard_clauses}
        seen: set[tuple[int, int]] = set()
        count = 0
        db.query(TocMatchItem).filter(TocMatchItem.job_id == job.id).delete(synchronize_session=False)
        for match in matches:
            standard_clause_id = _int_or_none(match.get("standard_clause_id"))
            plan_section_id = _int_or_none(match.get("plan_section_id"))
            if not standard_clause_id or not plan_section_id:
                continue
            if standard_clause_id not in clause_by_id or plan_section_id not in plan_by_id:
                continue
            key = (standard_clause_id, plan_section_id)
            if key in seen:
                continue
            seen.add(key)
            db.add(
                TocMatchItem(
                    job_id=job.id,
                    standard_id=job.standard_id,
                    standard_clause_id=standard_clause_id,
                    plan_document_id=job.plan_document_id,
                    plan_section_id=plan_section_id,
                    match_type=str(match.get("match_type") or "semantic")[:50],
                    confidence=_confidence(match.get("confidence")),
                    reason=str(match.get("reason") or "")[:2000] or None,
                )
            )
            count += 1
        job.match_count = count
        db.flush()


def _plan_toc_payload(sections: list[PlanSection]) -> list[dict[str, Any]]:
    section_by_id = {section.id: section for section in sections}
    return [
        {
            "id": section.id,
            "parent_id": section.parent_id if section.parent_id in section_by_id else None,
            "level": section.level,
            "section_no": section.section_no,
            "title": section.title,
            "path": _section_path(section, section_by_id),
        }
        for section in sections
    ]


def _standard_toc_payload(clauses: list[StandardClause]) -> list[dict[str, Any]]:
    clause_by_id = {clause.id: clause for clause in clauses}
    return [
        {
            "id": clause.id,
            "parent_id": clause.parent_id if clause.parent_id in clause_by_id else None,
            "level": clause.level,
            "clause_no": clause.clause_no,
            "title": clause.title,
            "path": clause.path or _clause_path(clause, clause_by_id),
        }
        for clause in clauses
    ]


def _section_path(section: PlanSection, section_by_id: dict[int, PlanSection]) -> str:
    parts = [section.title]
    parent_id = section.parent_id
    while parent_id and parent_id in section_by_id:
        parent = section_by_id[parent_id]
        parts.append(parent.title)
        parent_id = parent.parent_id
    return " / ".join(reversed([part for part in parts if part]))


def _clause_path(clause: StandardClause, clause_by_id: dict[int, StandardClause]) -> str:
    parts = [clause.title or clause.clause_no or ""]
    parent_id = clause.parent_id
    while parent_id and parent_id in clause_by_id:
        parent = clause_by_id[parent_id]
        parts.append(parent.title or parent.clause_no or "")
        parent_id = parent.parent_id
    return " / ".join(reversed([part for part in parts if part]))


def _extract_matches(response: dict[str, Any]) -> list[dict[str, Any]]:
    parsed = response.get("parsed")
    if isinstance(parsed, dict) and isinstance(parsed.get("matches"), list):
        return [item for item in parsed["matches"] if isinstance(item, dict)]
    content = response.get("content")
    if isinstance(content, str):
        return _salvage_match_objects(content)
    return []


def _loads_json_object(content: str) -> tuple[Any, str | None]:
    if not content:
        return None, None
    cleaned = _strip_json_wrappers(content)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as first_exc:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            salvaged = _salvage_match_objects(cleaned)
            return {"matches": salvaged}, str(first_exc)
        try:
            return json.loads(match.group(0)), None
        except json.JSONDecodeError as second_exc:
            salvaged = _salvage_match_objects(match.group(0))
            return {"matches": salvaged}, str(second_exc)


def _strip_json_wrappers(content: str) -> str:
    cleaned = content.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.S | re.I)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    return cleaned


def _salvage_match_objects(content: str) -> list[dict[str, Any]]:
    cleaned = _strip_json_wrappers(content)
    matches: list[dict[str, Any]] = []
    for object_text in re.findall(r"\{[^{}]*\"standard_clause_id\"[^{}]*\"plan_section_id\"[^{}]*\}", cleaned, flags=re.S):
        try:
            item = json.loads(object_text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            matches.append(item)
    return matches


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(number, 1.0))


def get_toc_matcher_service() -> Generator[TocMatcherService, None, None]:
    yield TocMatcherService()
