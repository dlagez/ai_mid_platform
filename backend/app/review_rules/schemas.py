from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateRuleCandidatesRequest(BaseModel):
    clause_ids: list[int]
    use_llm: bool = True


class GenerateRuleCandidatesResponse(BaseModel):
    created_count: int
    candidate_ids: list[int]
    failed: list[dict]
    skipped: list[dict]


class ReviewRuleCandidateUpdate(BaseModel):
    rule_name: str | None = None
    rule_type: str | None = None
    work_type: str | None = None
    check_object: str | None = None
    operator: str | None = None
    threshold_value: str | None = None
    unit: str | None = None
    required_items: list[str] | None = None
    forbidden_items: list[str] | None = None
    applicable_condition: dict | None = None
    risk_level_suggestion: str | None = None
    ai_confidence: float | None = None
    ai_reason: str | None = None
    status: str | None = None


class ReviewRuleCandidateRead(BaseModel):
    id: int
    standard_id: int | None
    clause_id: int | None
    rule_name: str | None
    rule_type: str | None
    work_type: str | None
    check_object: str | None
    operator: str | None
    threshold_value: str | None
    unit: str | None
    required_items: list
    forbidden_items: list
    applicable_condition: dict
    risk_level_suggestion: str | None
    source_clause_text: str | None
    ai_confidence: float | None
    ai_reason: str | None
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewRuleCandidateList(BaseModel):
    items: list[ReviewRuleCandidateRead]
    total: int
    page: int
    page_size: int


class ReviewRuleRead(BaseModel):
    id: int
    source_candidate_id: int | None
    source_type: str | None
    standard_id: int | None
    clause_id: int | None
    rule_name: str
    rule_type: str
    work_type: str | None
    check_object: str | None
    operator: str | None
    threshold_value: str | None
    unit: str | None
    required_items: list
    forbidden_items: list
    applicable_condition: dict
    risk_level: str
    status: str
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
