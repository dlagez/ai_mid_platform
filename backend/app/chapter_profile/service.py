from __future__ import annotations

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
    PlanSection,
    ReviewTask,
)
from app.services.model_service import ModelService
from app.utils.exceptions import PlatformError


CHAPTER_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("project_overview", ("工程概况", "项目概况", "工程简介")),
    ("basis", ("编制依据", "依据", "规范依据")),
    ("construction_deployment", ("施工部署", "施工安排", "组织部署")),
    ("construction_plan", ("施工计划", "进度计划", "资源计划")),
    ("construction_technology", ("施工工艺", "施工技术", "工艺技术", "施工方法", "施工流程", "主要施工方法")),
    ("quality_control", ("质量保证", "质量控制", "质量管理", "验收")),
    ("safety_control", ("安全保证", "安全措施", "安全管理", "危险源", "风险控制")),
    ("emergency", ("应急预案", "应急处置", "救援预案")),
    ("calculation", ("计算书", "验算", "荷载", "承载力", "稳定性")),
)

DOMAIN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("template_support", ("模板", "支撑架", "脚手架", "盘扣", "架体", "立杆", "剪刀撑")),
    ("concrete", ("混凝土", "浇筑", "振捣", "养护")),
    ("foundation", ("基础", "地基", "承载力", "垫板", "底座")),
    ("demolition", ("拆除", "拆架", "拆模")),
)

EXPECTED_BY_CHAPTER_TYPE: dict[str, list[str]] = {
    "construction_technology": ["基础构造", "架体参数", "剪刀撑", "搭设", "拆除", "浇筑", "验收"],
    "safety_control": ["危险源", "安全防护", "应急措施", "监测"],
    "calculation": ["荷载", "承载力", "稳定性", "参数取值"],
}

PROFILE_EXTRACTION_PROMPT = """你是一名施工方案审查画像抽取助手。
请基于章节标题和正文抽取结构化画像，只输出 JSON，不要输出 Markdown。

要求：
1. 只能基于原文抽取，不要编造结论。
2. materials、mentioned_parameters、mentioned_methods、mentioned_risks、mentioned_standards、expected_missing_objects 均输出字符串数组。
3. confidence 为 0-1 小数。

章节标题：{title}
章节类型：{chapter_type}
章节正文：
{content}

输出格式：
{{
  "materials": [],
  "mentioned_parameters": [],
  "mentioned_methods": [],
  "mentioned_risks": [],
  "mentioned_standards": [],
  "expected_missing_objects": [],
  "summary": "",
  "confidence": 0.0
}}
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

    def create_generation_job(self, db: Session, document_id: int, created_by: int | None = None) -> ChapterProfileGenerationJob:
        document = self._ensure_construction_plan_document(db, document_id)
        sections = (
            db.query(PlanSection)
            .filter(PlanSection.document_id == document.id)
            .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
            .all()
        )
        if not sections:
            raise PlatformError("The review task document has no parsed sections.", status_code=400)

        section_map = {section.id: section for section in sections}
        job = ChapterProfileGenerationJob(
            document_id=document.id,
            status="queued",
            total_sections=len(sections),
            created_by=created_by,
        )
        db.add(job)
        db.flush()
        for section in sections:
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

        async_result = generate_chapter_profiles_job.delay(job.id)
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

    async def run_generation_job(self, db: Session, job_id: int) -> dict[str, Any]:
        job = self.get_generation_job(db, job_id)
        if job.status in {"success", "partial_success", "failed"}:
            return {"job_id": job.id, "status": job.status}

        job.status = "running"
        job.started_at = job.started_at or datetime.utcnow()
        job.updated_at = datetime.utcnow()
        db.commit()

        try:
            sections = (
                db.query(PlanSection)
                .filter(PlanSection.document_id == job.document_id)
                .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
                .all()
            )
            section_map = {section.id: section for section in sections}
            section_by_id = {section.id: section for section in sections}
            items = (
                db.query(ChapterProfileGenerationItem)
                .filter(ChapterProfileGenerationItem.job_id == job.id)
                .order_by(ChapterProfileGenerationItem.id.asc())
                .all()
            )
            for item in items:
                if item.status == "success":
                    continue
                item.status = "running"
                item.started_at = item.started_at or datetime.utcnow()
                item.updated_at = datetime.utcnow()
                db.commit()

                section = section_by_id.get(item.section_id or 0)
                if not section:
                    item.status = "failed"
                    item.message = "Section not found."
                    item.finished_at = datetime.utcnow()
                    item.updated_at = datetime.utcnow()
                    self._refresh_generation_job_summary(db, job)
                    db.commit()
                    continue

                try:
                    profile, created, llm_failed = await self._upsert_profile_for_section(
                        db,
                        section=section,
                        section_map=section_map,
                        document_id=job.document_id,
                        task_id=job.task_id,
                    )
                    item.status = "rule_only" if llm_failed else "success"
                    item.profile_id = profile.id
                    item.used_llm = not llm_failed
                    item.confidence = profile.confidence
                    action = "created" if created else "updated"
                    item.message = f"Profile {action}; LLM failed, rule-only profile saved." if llm_failed else f"Profile {action}."
                    item.finished_at = datetime.utcnow()
                    item.updated_at = datetime.utcnow()
                    self._refresh_generation_job_summary(db, job)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    job = self.get_generation_job(db, job_id)
                    item = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.id == item.id).first()
                    if item:
                        item.status = "failed"
                        item.message = str(exc)
                        item.finished_at = datetime.utcnow()
                        item.updated_at = datetime.utcnow()
                    self._refresh_generation_job_summary(db, job)
                    db.commit()
            self._refresh_generation_job_summary(db, job)
            job.finished_at = datetime.utcnow()
            if job.failed_count >= job.total_sections:
                job.status = "failed"
            elif job.failed_count > 0 or job.rule_only_count > 0:
                job.status = "partial_success"
            else:
                job.status = "success"
            job.updated_at = datetime.utcnow()
            db.commit()
            return {"job_id": job.id, "status": job.status}
        except Exception as exc:
            db.rollback()
            job = self.get_generation_job(db, job_id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            db.commit()
            raise

    async def _build_profiles_for_document(self, db: Session, *, document_id: int, task_id: int | None) -> dict[str, Any]:
        sections = (
            db.query(PlanSection)
            .filter(PlanSection.document_id == document_id)
            .order_by(PlanSection.sort_no.asc(), PlanSection.id.asc())
            .all()
        )
        if not sections:
            raise PlatformError("The review task document has no parsed sections.", status_code=400)

        section_map = {section.id: section for section in sections}
        created_count = 0
        updated_count = 0
        failed: list[dict[str, Any]] = []
        saved: list[ChapterReviewProfile] = []

        for section in sections:
            try:
                profile, created, llm_failed = await self._upsert_profile_for_section(
                    db,
                    section=section,
                    section_map=section_map,
                    document_id=document_id,
                    task_id=task_id,
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                if llm_failed:
                    failed.append({"section_id": section.id, "reason": "LLM failed; rule-only profile saved."})
                saved.append(profile)
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

    async def _upsert_profile_for_section(
        self,
        db: Session,
        *,
        section: PlanSection,
        section_map: dict[int, PlanSection],
        document_id: int,
        task_id: int | None,
    ) -> tuple[ChapterReviewProfile, bool, bool]:
        text = f"{section.title}\n{section.content or ''}"
        chapter_type = _detect_chapter_type(section.title, section.content)
        objects = recognize_construction_objects(db, text)
        main_domain = _detect_main_domain(text)
        subdomains = _collect_subdomains(objects, text)
        missing = _expected_missing_objects(chapter_type, objects)

        ai_data: dict[str, Any] = {}
        llm_failed = False
        try:
            ai_data = await self._extract_profile_by_llm(section, chapter_type)
        except Exception:
            llm_failed = True

        query = db.query(ChapterReviewProfile).filter(
            ChapterReviewProfile.document_id == document_id,
            ChapterReviewProfile.section_id == section.id,
        )
        if task_id is None:
            query = query.filter(ChapterReviewProfile.task_id.is_(None))
        else:
            query = query.filter(ChapterReviewProfile.task_id == task_id)
        existing = query.first()
        values = {
            "task_id": task_id,
            "document_id": document_id,
            "section_id": section.id,
            "chapter_title": section.title,
            "chapter_path": _build_chapter_path(section, section_map),
            "chapter_type": chapter_type,
            "main_domain": main_domain,
            "subdomains": subdomains,
            "construction_objects": objects,
            "materials": _as_list(ai_data.get("materials")),
            "mentioned_parameters": _merge_lists(
                _as_list(ai_data.get("mentioned_parameters")),
                _object_related_values(objects, "related_parameters"),
                _extract_parameter_names(text),
            ),
            "mentioned_methods": _merge_lists(
                _as_list(ai_data.get("mentioned_methods")),
                _object_related_values(objects, "related_scenarios"),
                _extract_methods(text),
            ),
            "mentioned_risks": _as_list(ai_data.get("mentioned_risks")),
            "mentioned_standards": _merge_lists(_as_list(ai_data.get("mentioned_standards")), _extract_standards(text)),
            "expected_missing_objects": _merge_lists(missing, _as_list(ai_data.get("expected_missing_objects"))),
            "summary": ai_data.get("summary") or _fallback_summary(section, chapter_type, objects),
            "confidence": _as_confidence(ai_data.get("confidence"), default=0.55 if ai_data else 0.35),
            "updated_at": datetime.utcnow(),
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            db.flush()
            return existing, False, llm_failed
        row = ChapterReviewProfile(**values)
        db.add(row)
        db.flush()
        return row, True, llm_failed

    def _ensure_construction_plan_document(self, db: Session, document_id: int) -> PlanDocument:
        document = db.query(PlanDocument).filter(PlanDocument.id == document_id).first()
        if not document:
            raise PlatformError(f"Document id={document_id} not found", status_code=404)
        if document.document_type != "construction_plan":
            raise PlatformError("Chapter profiles can only be generated for construction plan documents.", status_code=400)
        if document.parse_status != "parsed":
            raise PlatformError("Document must be parsed before generating chapter profiles.", status_code=400)
        return document

    def _refresh_generation_job_summary(self, db: Session, job: ChapterProfileGenerationJob) -> None:
        items = db.query(ChapterProfileGenerationItem).filter(ChapterProfileGenerationItem.job_id == job.id).all()
        success_statuses = {"success", "rule_only", "failed"}
        job.processed_sections = sum(1 for item in items if item.status in success_statuses)
        job.created_count = sum(1 for item in items if item.status in {"success", "rule_only"} and item.profile_id and "created" in (item.message or ""))
        job.updated_count = sum(1 for item in items if item.status in {"success", "rule_only"} and item.profile_id and "updated" in (item.message or ""))
        job.failed_count = sum(1 for item in items if item.status == "failed")
        job.rule_only_count = sum(1 for item in items if item.status == "rule_only")
        job.updated_at = datetime.utcnow()

    async def _extract_profile_by_llm(self, section: PlanSection, chapter_type: str | None) -> dict[str, Any]:
        content = (section.content or "")[:4000]
        if not content.strip():
            return {}
        model_service = ModelService()
        result = await model_service.call_model(
            {
                "model": model_service.default_model,
                "messages": [
                    {
                        "role": "user",
                        "content": PROFILE_EXTRACTION_PROMPT.format(
                            title=section.title or "",
                            chapter_type=chapter_type or "",
                            content=content,
                        ),
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 1200,
            }
        )
        content = ((result.get("output") or {}).get("content") or "").strip()
        return _parse_json_object(content)


def _detect_chapter_type(title: str | None, content: str | None = None) -> str | None:
    text = f"{title or ''}\n{(content or '')[:500]}"
    for chapter_type, keywords in CHAPTER_TYPE_RULES:
        if any(keyword in text for keyword in keywords):
            return chapter_type
    return "other"


def _detect_main_domain(text: str) -> str | None:
    for domain, keywords in DOMAIN_RULES:
        if any(keyword in text for keyword in keywords):
            return domain
    return None


def _collect_subdomains(objects: list[dict[str, Any]], text: str) -> list[str]:
    values = [str(item.get("object_type")) for item in objects if item.get("object_type")]
    if "盘扣" in text:
        values.append("盘扣式支撑体系")
    if "剪刀撑" in text:
        values.append("架体构造")
    if "浇筑" in text:
        values.append("混凝土浇筑")
    return _merge_lists(values)


def _expected_missing_objects(chapter_type: str | None, objects: list[dict[str, Any]]) -> list[str]:
    expected = EXPECTED_BY_CHAPTER_TYPE.get(chapter_type or "", [])
    object_text = " ".join(str(item.get("object_name", "")) + " " + " ".join(item.get("matched_terms") or []) for item in objects)
    return [item for item in expected if item not in object_text]


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


def _object_related_values(objects: list[dict[str, Any]], key: str) -> list[str]:
    values: list[str] = []
    for item in objects:
        values.extend(str(value) for value in item.get(key) or [])
    return values


def _extract_parameter_names(text: str) -> list[str]:
    candidates = ("立杆间距", "步距", "架体高度", "自由端高度", "可调托撑", "承载力", "搭接长度", "浇筑速度", "分层厚度")
    return [item for item in candidates if item in text]


def _extract_methods(text: str) -> list[str]:
    candidates = ("搭设", "拆除", "浇筑", "验收", "监测", "基础处理", "安全防护", "排水", "振捣")
    return [item for item in candidates if item in text]


def _extract_standards(text: str) -> list[str]:
    pattern = re.compile(r"(?:GB|JGJ|DB|T/CECS)\s*[\d/T.-]+(?:-\d{4})?", re.IGNORECASE)
    return _merge_lists(match.group(0).strip() for match in pattern.finditer(text or ""))


def _fallback_summary(section: PlanSection, chapter_type: str | None, objects: list[dict[str, Any]]) -> str:
    object_names = "、".join(str(item.get("object_name")) for item in objects if item.get("object_name"))
    return f"章节类型：{chapter_type or 'other'}；施工对象：{object_names or '未识别'}；标题：{section.title or ''}"


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
