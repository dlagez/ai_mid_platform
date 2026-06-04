from __future__ import annotations

import json
import io
import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    ParseResultSection,
    PlanDocument,
    PlanParseResult,
    PlanSection,
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
{"matches":[{"standard_section_id":1,"plan_section_id":2,"confidence":0.85,"reason":"简短中文理由"}]}

施工方案目录（一二级）：
{plan_toc}

规范目录（一二级）：
{standard_toc}
"""


TOC_REVIEW_PROMPT = """你是一名施工方案规范审查专家。

任务：根据“标准规范章节内容”审查“施工方案对应章节内容”，找出施工方案中缺失、冲突、不满足规范要求或证据不足的问题。

输出要求：
1. 只输出单行紧凑 JSON，不要 Markdown，不要解释文字，不要代码块。
2. 顶层必须是对象，且只包含 issues 数组。
3. 如果未发现问题，输出 {"issues":[]}。
4. 每个 issue 必须包含 standard_basis、plan_evidence、problem_description、rectification_suggestion 四个字段。
5. standard_basis 应引用具体规范条款或要求；不得编造输入中不存在的规范要求。
6. plan_evidence 应引用施工方案中的关键证据；若施工方案未找到对应要求，应明确写“未在施工方案本章节中找到……”。
7. problem_description 应说明施工方案的问题，不要写泛泛风险。
8. rectification_suggestion 应给出可执行的补充或整改建议。

标准名称：
{standard_name}

标准规范章节内容：
{standard_content}

施工方案章节：
{plan_title}

施工方案章节内容：
{plan_content}

输出格式：
{"issues":[{"standard_basis":"7.1.2 模板拆除前应确认混凝土强度达到设计或规范要求。","plan_evidence":"未在施工方案本章节中找到模板拆除前混凝土强度确认要求。","problem_description":"施工方案未明确模板拆除前混凝土强度应达到设计或规范要求。","rectification_suggestion":"建议补充模板拆除前混凝土强度确认要求，明确拆除前应核查同条件养护试块强度报告或相关验收资料。"}]}
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
        standard_sections = self._get_standard_toc_sections(db, standard)
        if not plan_sections:
            raise PlatformError("The construction plan has no parsed level-1/2 sections.", status_code=400)
        if not standard_sections:
            raise PlatformError("The standard has no parsed level-1/2 sections.", status_code=400)

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
            response = await self._call_llm(plan_sections, standard_sections, model=model, job=job)
            job.raw_llm_response = response
            matches = _extract_matches(response)
            self._persist_matches(db, job, matches, plan_sections, standard_sections)
            job.status = "reviewing"
            db.commit()
            self._refresh_for_review(db, job)
            await self._review_matches(db, job, model=model)
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
            .options(joinedload(TocMatchItem.standard_section), joinedload(TocMatchItem.plan_section))
            .filter(TocMatchItem.job_id == job.id)
            .order_by(TocMatchItem.id.asc())
            .all()
        )
        return job, items

    def export_review_issues_to_excel(self, db: Session, job_id: int) -> tuple[io.BytesIO, str]:
        job, _ = self.get_job_detail(db, job_id)
        items = (
            db.query(TocMatchItem)
            .options(joinedload(TocMatchItem.standard_section), joinedload(TocMatchItem.plan_section))
            .filter(TocMatchItem.job_id == job.id)
            .order_by(TocMatchItem.id.asc())
            .all()
        )
        standard_by_parent, plan_by_parent = self._get_review_context(db, job)

        wb = Workbook()
        ws = wb.active
        ws.title = "Review Issues"
        ws.append(["序号", "方案标题", "方案内容", "标准标题", "标准内容", "问题", "解决方案"])

        row_no = 1
        for item in items:
            issues = item.review_issues or []
            if not issues:
                continue
            plan_title = _format_plan_title(item.plan_section)
            standard_title = _format_standard_title(item.standard_section)
            plan_content = _subtree_content(item.plan_section, plan_by_parent, "plan")
            standard_content = _subtree_content(item.standard_section, standard_by_parent, "standard")
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                ws.append(
                    [
                        row_no,
                        _sanitize_cell(plan_title),
                        _sanitize_cell(plan_content),
                        _sanitize_cell(standard_title),
                        _sanitize_cell(standard_content),
                        _sanitize_cell(str(issue.get("problem_description") or "")),
                        _sanitize_cell(str(issue.get("rectification_suggestion") or "")),
                    ]
                )
                row_no += 1

        for column, width in {
            "A": 8,
            "B": 34,
            "C": 80,
            "D": 34,
            "E": 80,
            "F": 54,
            "G": 54,
        }.items():
            ws.column_dimensions[column].width = width

        filename = f"toc_match_job_{job.id}_issues.xlsx"
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer, filename

    async def review_job(self, db: Session, job_id: int, *, model: str | None = None) -> TocMatchJob:
        job, _ = self.get_job_detail(db, job_id)
        job.status = "reviewing"
        job.error_message = None
        job.completed_at = None
        db.commit()
        db.refresh(job)

        try:
            await self._review_matches(db, job, model=model or job.model)
            self._refresh_review_counts(db, job)
            job.status = "success"
            job.error_message = None
            job.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
            return job
        except Exception as exc:
            db.rollback()
            failed = db.query(TocMatchJob).filter(TocMatchJob.id == job_id).first()
            if failed:
                failed.status = "failed"
                failed.error_message = str(exc)
                failed.completed_at = datetime.utcnow()
                db.commit()
                db.refresh(failed)
                return failed
            raise

    async def review_item(self, db: Session, item_id: int, *, model: str | None = None) -> TocMatchItem:
        item = (
            db.query(TocMatchItem)
            .options(
                joinedload(TocMatchItem.job).joinedload(TocMatchJob.standard),
                joinedload(TocMatchItem.standard_section),
                joinedload(TocMatchItem.plan_section),
            )
            .filter(TocMatchItem.id == item_id)
            .first()
        )
        if not item:
            raise PlatformError(f"TOC match item id={item_id} not found", status_code=404)
        job = item.job
        job.status = "reviewing"
        job.error_message = None
        item.review_status = "running"
        item.review_error = None
        db.commit()
        db.refresh(item)

        standard_by_parent, plan_by_parent = self._get_review_context(db, job)
        await self._review_single_item(
            db,
            job,
            item,
            standard_by_parent=standard_by_parent,
            plan_by_parent=plan_by_parent,
            model=model or job.model,
        )
        self._refresh_review_counts(db, job)
        job.status = "success"
        job.completed_at = datetime.utcnow()
        db.commit()
        refreshed = (
            db.query(TocMatchItem)
            .options(joinedload(TocMatchItem.standard_section), joinedload(TocMatchItem.plan_section))
            .filter(TocMatchItem.id == item_id)
            .first()
        )
        if not refreshed:
            raise PlatformError(f"TOC match item id={item_id} not found", status_code=404)
        return refreshed

    def _refresh_for_review(self, db: Session, job: TocMatchJob) -> None:
        db.refresh(job)

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

    def _get_standard_toc_sections(self, db: Session, standard: StandardDocument) -> list[ParseResultSection]:
        if not standard.source_document_id:
            raise PlatformError("The selected standard has no source parse result.", status_code=400)
        return (
            db.query(ParseResultSection)
            .filter(ParseResultSection.document_id == standard.source_document_id, ParseResultSection.title_level <= 2)
            .order_by(ParseResultSection.sort_no.asc(), ParseResultSection.id.asc())
            .all()
        )

    def _get_standard_sections(self, db: Session, standard: StandardDocument) -> list[ParseResultSection]:
        if not standard.source_document_id:
            raise PlatformError("The selected standard has no source parse result.", status_code=400)
        return (
            db.query(ParseResultSection)
            .filter(ParseResultSection.document_id == standard.source_document_id)
            .order_by(ParseResultSection.sort_no.asc(), ParseResultSection.id.asc())
            .all()
        )

    async def _call_llm(
        self,
        plan_sections: list[PlanSection],
        standard_sections: list[ParseResultSection],
        *,
        model: str | None = None,
        job: TocMatchJob | None = None,
    ) -> dict[str, Any]:
        prompt = TOC_MATCH_PROMPT.replace("{plan_toc}", json.dumps(_plan_toc_payload(plan_sections), ensure_ascii=False))
        prompt = prompt.replace("{standard_toc}", json.dumps(_standard_toc_payload(standard_sections), ensure_ascii=False))
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
            "standard_toc_count": len(standard_sections),
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
        standard_sections: list[ParseResultSection],
    ) -> None:
        plan_by_id = {section.id: section for section in plan_sections}
        standard_by_id = {section.id: section for section in standard_sections}
        seen: set[tuple[int, int]] = set()
        count = 0
        db.query(TocMatchItem).filter(TocMatchItem.job_id == job.id).delete(synchronize_session=False)
        for match in matches:
            standard_section_id = _int_or_none(match.get("standard_section_id"))
            plan_section_id = _int_or_none(match.get("plan_section_id"))
            if not standard_section_id or not plan_section_id:
                continue
            if standard_section_id not in standard_by_id or plan_section_id not in plan_by_id:
                continue
            key = (standard_section_id, plan_section_id)
            if key in seen:
                continue
            seen.add(key)
            db.add(
                TocMatchItem(
                    job_id=job.id,
                    standard_id=job.standard_id,
                    standard_section_id=standard_section_id,
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

    async def _review_matches(self, db: Session, job: TocMatchJob, *, model: str | None = None) -> None:
        items = (
            db.query(TocMatchItem)
            .options(joinedload(TocMatchItem.standard_section), joinedload(TocMatchItem.plan_section))
            .filter(TocMatchItem.job_id == job.id)
            .order_by(TocMatchItem.id.asc())
            .all()
        )
        if not items:
            job.reviewed_count = 0
            job.issue_count = 0
            db.flush()
            return

        standard_by_parent, plan_by_parent = self._get_review_context(db, job)

        reviewed_count = 0
        issue_count = 0
        for item in items:
            await self._review_single_item(
                db,
                job,
                item,
                standard_by_parent=standard_by_parent,
                plan_by_parent=plan_by_parent,
                model=model,
            )
            if item.review_status == "success":
                reviewed_count += 1
                issue_count += len(item.review_issues or [])
            job.reviewed_count = reviewed_count
            job.issue_count = issue_count
            db.flush()

    def _get_review_context(
        self,
        db: Session,
        job: TocMatchJob,
    ) -> tuple[dict[int | None, list[ParseResultSection]], dict[int | None, list[PlanSection]]]:
        standard_sections = self._get_standard_sections(db, job.standard)
        plan_sections = (
            db.query(PlanSection)
            .filter(
                PlanSection.document_id == job.plan_document_id,
                PlanSection.parse_result_id == job.plan_parse_result_id,
            )
            .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
            .all()
        )
        return _group_by_parent(standard_sections), _group_by_parent(plan_sections)

    async def _review_single_item(
        self,
        db: Session,
        job: TocMatchJob,
        item: TocMatchItem,
        *,
        standard_by_parent: dict[int | None, list[ParseResultSection]],
        plan_by_parent: dict[int | None, list[PlanSection]],
        model: str | None = None,
    ) -> None:
        try:
            item.review_status = "running"
            item.review_error = None
            db.flush()
            standard_content = _subtree_content(item.standard_section, standard_by_parent, "standard")
            plan_content = _subtree_content(item.plan_section, plan_by_parent, "plan")
            response = await self._call_review_llm(
                item,
                standard_name=job.standard.standard_name if job.standard else "",
                standard_content=standard_content,
                plan_content=plan_content,
                model=model,
            )
            item.raw_review_response = response
            issues = _extract_review_issues(response)
            item.review_issues = issues
            item.review_status = "success"
            item.review_error = None
            item.reviewed_at = datetime.utcnow()
        except Exception as exc:
            item.review_status = "failed"
            item.review_error = str(exc)
            item.reviewed_at = datetime.utcnow()
        db.flush()

    def _refresh_review_counts(self, db: Session, job: TocMatchJob) -> None:
        items = db.query(TocMatchItem).filter(TocMatchItem.job_id == job.id).all()
        job.reviewed_count = sum(1 for item in items if item.review_status == "success")
        job.issue_count = sum(len(item.review_issues or []) for item in items if item.review_status == "success")
        db.flush()

    async def _call_review_llm(
        self,
        item: TocMatchItem,
        *,
        standard_name: str,
        standard_content: str,
        plan_content: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        service = ModelService()
        model_name = model or service.default_model
        standard = item.standard_section
        plan = item.plan_section
        prompt = TOC_REVIEW_PROMPT.replace("{standard_name}", standard_name or "")
        prompt = prompt.replace("{standard_content}", _truncate(standard_content, 9000))
        prompt = prompt.replace("{plan_title}", _format_plan_title(plan))
        prompt = prompt.replace("{plan_content}", _truncate(plan_content, 9000))
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 3000,
        }
        metadata = {
            "operation": "toc_matching.review",
            "job_id": item.job_id,
            "match_item_id": item.id,
            "standard_section_id": item.standard_section_id,
            "plan_section_id": item.plan_section_id,
            "standard_section_no": standard.section_no if standard else None,
            "plan_section_no": plan.section_no if plan else None,
            "prompt_chars": len(prompt),
        }
        with langfuse_observation(
            name="toc_matching.review",
            input_data={"messages": payload["messages"]},
            metadata=metadata,
            session_id=f"toc-match-job:{item.job_id}",
            tags=["toc_matching", "toc_review", "llm"],
            as_type="generation",
            model=model_name,
        ) as observation:
            response = await service.call_model(payload)
            content = ((response.get("output") or {}).get("content") or "").strip()
            parsed, parse_error = _loads_json_object(content)
            result_payload: dict[str, Any] = {"model_response": response, "content": content, "parsed": parsed}
            if parse_error:
                result_payload["parse_error"] = parse_error
            issues = _extract_review_issues(result_payload)
            update_langfuse_observation(
                observation,
                output={"content": content},
                metadata=metadata
                | {
                    "provider": response.get("provider"),
                    "model": response.get("model"),
                    "output_chars": len(content),
                    "parse_error": parse_error,
                    "issue_count": len(issues),
                },
            )
        return result_payload


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


def _standard_toc_payload(sections: list[ParseResultSection]) -> list[dict[str, Any]]:
    section_by_id = {section.id: section for section in sections}
    return [
        {
            "id": section.id,
            "parent_id": section.parent_id if section.parent_id in section_by_id else None,
            "level": section.title_level,
            "section_no": section.section_no,
            "title": section.title,
            "path": _parse_section_path(section, section_by_id),
        }
        for section in sections
    ]


def _section_path(section: PlanSection, section_by_id: dict[int, PlanSection]) -> str:
    parts = [section.title]
    parent_id = section.parent_id
    while parent_id and parent_id in section_by_id:
        parent = section_by_id[parent_id]
        parts.append(parent.title)
        parent_id = parent.parent_id
    return " / ".join(reversed([part for part in parts if part]))


def _parse_section_path(section: ParseResultSection, section_by_id: dict[int, ParseResultSection]) -> str:
    parts = [section.title]
    parent_id = section.parent_id
    while parent_id and parent_id in section_by_id:
        parent = section_by_id[parent_id]
        parts.append(parent.title)
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
    for object_text in re.findall(r"\{[^{}]*\"standard_section_id\"[^{}]*\"plan_section_id\"[^{}]*\}", cleaned, flags=re.S):
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


def _group_by_parent(items: list[Any]) -> dict[int | None, list[Any]]:
    grouped: dict[int | None, list[Any]] = {}
    for item in items:
        grouped.setdefault(getattr(item, "parent_id", None), []).append(item)
    return grouped


def _subtree_content(root: Any, by_parent: dict[int | None, list[Any]], kind: str) -> str:
    if not root:
        return ""
    lines: list[str] = []

    def visit(node: Any) -> None:
        title = _format_standard_title(node) if kind == "standard" else _format_plan_title(node)
        content = str(getattr(node, "content", "") or "").strip()
        if title:
            lines.append(f"## {title}")
        if content:
            lines.append(content)
        for child in by_parent.get(getattr(node, "id", None), []):
            visit(child)

    visit(root)
    return "\n\n".join(line for line in lines if line).strip()


def _format_standard_title(section: ParseResultSection | None) -> str:
    if not section:
        return ""
    return " ".join(str(part).strip() for part in (section.section_no, section.title) if part)


def _format_plan_title(section: PlanSection | None) -> str:
    if not section:
        return ""
    return " ".join(str(part).strip() for part in (section.section_no, section.title) if part)


def _extract_review_issues(response: dict[str, Any]) -> list[dict[str, str]]:
    parsed = response.get("parsed")
    if isinstance(parsed, dict) and isinstance(parsed.get("issues"), list):
        return [_normalize_issue(item) for item in parsed["issues"] if isinstance(item, dict)]
    content = response.get("content")
    if isinstance(content, str):
        parsed_content, _ = _loads_json_object(content)
        if isinstance(parsed_content, dict) and isinstance(parsed_content.get("issues"), list):
            return [_normalize_issue(item) for item in parsed_content["issues"] if isinstance(item, dict)]
    return []


def _normalize_issue(item: dict[str, Any]) -> dict[str, str]:
    return {
        "standard_basis": str(item.get("standard_basis") or "").strip(),
        "plan_evidence": str(item.get("plan_evidence") or "").strip(),
        "problem_description": str(item.get("problem_description") or "").strip(),
        "rectification_suggestion": str(item.get("rectification_suggestion") or "").strip(),
    }


def _truncate(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[内容已截断]"


def _sanitize_cell(value: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value or ""))


def get_toc_matcher_service() -> Generator[TocMatcherService, None, None]:
    yield TocMatcherService()
