from __future__ import annotations

import json
import re
from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import ReviewRule, ReviewRuleCandidate, StandardClause, StandardDocument
from app.review_rules.schemas import GenerateRuleCandidatesRequest, ReviewRuleCandidateUpdate
from app.services.model_service import ModelService
from app.utils.exceptions import PlatformError

RULE_TYPES = {
    "required_section",
    "required_field",
    "required_keyword",
    "forbidden_keyword",
    "parameter_threshold",
    "procedure_required",
    "semantic_check",
}
CANDIDATE_STATUSES = {"pending_review", "approved", "rejected"}

RULE_EXTRACTION_PROMPT = """你是一名施工规范规则抽取助手。
任务：从规范条文中抽取可用于施工方案审核的候选规则。

要求：
1. 只能基于条文原文抽取，不得编造。
2. 如果条文是原则性、定义性、解释性内容，不要强行生成硬规则。
3. 参数类规则必须抽取检查对象、比较符、数值、单位。
4. 必填内容类规则必须抽取 required_items。
5. 禁止性条文必须抽取 forbidden_items。
6. 输出 JSON，不要输出 Markdown。
7. 所有规则状态均为 pending_review，需要专家确认后才能发布。

条文信息：
规范名称：{standard_name}
条文编号：{clause_no}
条文内容：{clause_content}

输出格式：
{{
  "can_generate_rule": true,
  "clause_type": "",
  "rule_type": "",
  "rule_name": "",
  "work_type": "",
  "check_object": "",
  "operator": "",
  "threshold_value": "",
  "unit": "",
  "required_items": [],
  "forbidden_items": [],
  "applicable_condition": {{}},
  "risk_level_suggestion": "",
  "ai_confidence": 0.0,
  "ai_reason": ""
}}

rule_type 只能从以下值中选择：
- required_section
- required_field
- required_keyword
- forbidden_keyword
- parameter_threshold
- procedure_required
- semantic_check
"""


class ReviewRuleService:
    async def generate_candidates(
        self,
        db: Session,
        standard_id: int,
        data: GenerateRuleCandidatesRequest,
    ) -> dict[str, Any]:
        standard = db.query(StandardDocument).filter(StandardDocument.id == standard_id).first()
        if not standard:
            raise PlatformError(f"Standard document id={standard_id} not found", status_code=404)

        clauses = (
            db.query(StandardClause)
            .filter(StandardClause.standard_id == standard_id, StandardClause.id.in_(data.clause_ids))
            .order_by(StandardClause.order_no.asc(), StandardClause.id.asc())
            .all()
        )
        found_ids = {clause.id for clause in clauses}
        failed = [
            {"clause_id": clause_id, "reason": "clause not found"}
            for clause_id in data.clause_ids
            if clause_id not in found_ids
        ]
        skipped: list[dict[str, Any]] = []
        candidate_ids: list[int] = []

        for clause in clauses:
            try:
                extracted = await self._extract_rule(standard, clause, use_llm=data.use_llm)
                if not extracted.get("can_generate_rule"):
                    skipped.append({"clause_id": clause.id, "reason": extracted.get("ai_reason") or "no rule generated"})
                    continue

                rule_type = extracted.get("rule_type") or "semantic_check"
                if rule_type not in RULE_TYPES:
                    rule_type = "semantic_check"

                candidate = ReviewRuleCandidate(
                    standard_id=standard.id,
                    clause_id=clause.id,
                    rule_name=extracted.get("rule_name") or self._default_rule_name(clause),
                    rule_type=rule_type,
                    work_type=extracted.get("work_type") or None,
                    check_object=extracted.get("check_object") or None,
                    operator=extracted.get("operator") or None,
                    threshold_value=extracted.get("threshold_value") or None,
                    unit=extracted.get("unit") or None,
                    required_items=self._as_list(extracted.get("required_items")),
                    forbidden_items=self._as_list(extracted.get("forbidden_items")),
                    applicable_condition=self._as_dict(extracted.get("applicable_condition")),
                    risk_level_suggestion=extracted.get("risk_level_suggestion") or "major",
                    source_clause_text=clause.content,
                    ai_confidence=self._as_confidence(extracted.get("ai_confidence")),
                    ai_reason=extracted.get("ai_reason") or "",
                    status="pending_review",
                )
                db.add(candidate)
                db.flush()
                candidate_ids.append(candidate.id)
            except Exception as exc:
                db.rollback()
                failed.append({"clause_id": clause.id, "reason": str(exc)})
            else:
                db.commit()

        return {
            "created_count": len(candidate_ids),
            "candidate_ids": candidate_ids,
            "failed": failed,
            "skipped": skipped,
        }

    def list_candidates(
        self,
        db: Session,
        *,
        status: str | None = None,
        standard_id: int | None = None,
        rule_type: str | None = None,
        work_type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewRuleCandidate], int]:
        query = db.query(ReviewRuleCandidate)
        if status:
            query = query.filter(ReviewRuleCandidate.status == status)
        if standard_id:
            query = query.filter(ReviewRuleCandidate.standard_id == standard_id)
        if rule_type:
            query = query.filter(ReviewRuleCandidate.rule_type == rule_type)
        if work_type:
            query = query.filter(ReviewRuleCandidate.work_type == work_type)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    ReviewRuleCandidate.rule_name.ilike(like),
                    ReviewRuleCandidate.source_clause_text.ilike(like),
                    ReviewRuleCandidate.ai_reason.ilike(like),
                )
            )
        total = query.count()
        items = (
            query.order_by(ReviewRuleCandidate.created_at.desc(), ReviewRuleCandidate.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_candidate(self, db: Session, candidate_id: int) -> ReviewRuleCandidate:
        candidate = db.query(ReviewRuleCandidate).filter(ReviewRuleCandidate.id == candidate_id).first()
        if not candidate:
            raise PlatformError(f"Rule candidate id={candidate_id} not found", status_code=404)
        return candidate

    def update_candidate(
        self,
        db: Session,
        candidate_id: int,
        data: ReviewRuleCandidateUpdate,
    ) -> ReviewRuleCandidate:
        candidate = self.get_candidate(db, candidate_id)
        values = data.model_dump(exclude_unset=True)
        if "status" in values and values["status"] not in CANDIDATE_STATUSES:
            raise PlatformError(f"Invalid candidate status: {values['status']}", status_code=400)
        if "rule_type" in values and values["rule_type"] and values["rule_type"] not in RULE_TYPES:
            raise PlatformError(f"Invalid rule type: {values['rule_type']}", status_code=400)
        for key, value in values.items():
            setattr(candidate, key, value)
        db.commit()
        db.refresh(candidate)
        return candidate

    def approve_candidate(
        self,
        db: Session,
        candidate_id: int,
        reviewed_by: int | None = None,
    ) -> tuple[ReviewRuleCandidate, ReviewRule]:
        candidate = self.get_candidate(db, candidate_id)
        if candidate.status == "approved":
            existing = db.query(ReviewRule).filter(ReviewRule.source_candidate_id == candidate.id).first()
            if existing:
                return candidate, existing
        if not candidate.rule_name or not candidate.rule_type:
            raise PlatformError("Candidate must have rule_name and rule_type before approval.", status_code=400)
        if candidate.rule_type not in RULE_TYPES:
            raise PlatformError(f"Invalid rule type: {candidate.rule_type}", status_code=400)

        candidate.status = "approved"
        candidate.reviewed_by = reviewed_by
        candidate.reviewed_at = datetime.utcnow()
        rule = ReviewRule(
            source_candidate_id=candidate.id,
            source_type="standard_clause",
            standard_id=candidate.standard_id,
            clause_id=candidate.clause_id,
            rule_name=candidate.rule_name,
            rule_type=candidate.rule_type,
            work_type=candidate.work_type,
            check_object=candidate.check_object,
            operator=candidate.operator,
            threshold_value=candidate.threshold_value,
            unit=candidate.unit,
            required_items=candidate.required_items or [],
            forbidden_items=candidate.forbidden_items or [],
            applicable_condition=candidate.applicable_condition or {},
            risk_level=candidate.risk_level_suggestion or "major",
            status="active",
            created_by=reviewed_by,
        )
        db.add(rule)
        db.commit()
        db.refresh(candidate)
        db.refresh(rule)
        return candidate, rule

    def reject_candidate(
        self,
        db: Session,
        candidate_id: int,
        reviewed_by: int | None = None,
    ) -> ReviewRuleCandidate:
        candidate = self.get_candidate(db, candidate_id)
        candidate.status = "rejected"
        candidate.reviewed_by = reviewed_by
        candidate.reviewed_at = datetime.utcnow()
        db.commit()
        db.refresh(candidate)
        return candidate

    async def _extract_rule(
        self,
        standard: StandardDocument,
        clause: StandardClause,
        *,
        use_llm: bool,
    ) -> dict[str, Any]:
        if not use_llm:
            return self._heuristic_extract(clause)

        prompt = RULE_EXTRACTION_PROMPT.format(
            standard_name=standard.standard_name,
            clause_no=clause.clause_no or "",
            clause_content=clause.content or "",
        )
        model_service = ModelService()
        result = await model_service.call_model(
            {
                "model": model_service.default_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1200,
            }
        )
        content = ((result.get("output") or {}).get("content") or "").strip()
        return _parse_json_object(content)

    def _heuristic_extract(self, clause: StandardClause) -> dict[str, Any]:
        content = clause.content or ""
        if not any(term in content for term in ("必须", "严禁", "不得", "应当", "应")):
            return {"can_generate_rule": False, "ai_reason": "条文未识别到明确约束。"}
        forbidden = [term for term in ("严禁", "不得") if term in content]
        return {
            "can_generate_rule": True,
            "rule_type": "forbidden_keyword" if forbidden else "semantic_check",
            "rule_name": self._default_rule_name(clause),
            "work_type": "",
            "check_object": clause.title or clause.clause_no or "",
            "operator": "",
            "threshold_value": "",
            "unit": "",
            "required_items": [] if forbidden else [content[:200]],
            "forbidden_items": forbidden,
            "applicable_condition": {},
            "risk_level_suggestion": "major",
            "ai_confidence": 0.5,
            "ai_reason": "未调用 LLM，按强约束词启发式生成。",
        }

    def _default_rule_name(self, clause: StandardClause) -> str:
        prefix = clause.clause_no or f"条文{clause.id}"
        title = clause.title or "施工规范要求"
        return f"{prefix} {title}"[:255]

    def _as_list(self, value: Any) -> list:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _as_dict(self, value: Any) -> dict:
        return value if isinstance(value, dict) else {}

    def _as_confidence(self, value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            confidence = float(value)
            return max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            return None


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


def get_review_rule_service() -> Generator[ReviewRuleService, None, None]:
    yield ReviewRuleService()
