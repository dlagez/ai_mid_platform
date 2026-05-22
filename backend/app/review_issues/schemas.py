from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewIssueRead(BaseModel):
    id: int
    task_id: int
    issue_type: str | None
    risk_level: str | None
    issue_title: str | None
    issue_description: str | None
    plan_section_id: int | None
    plan_section_title: str | None
    plan_original_text: str | None
    source_type: str | None
    source_rule_id: int | None
    source_template_rule_id: int | None
    standard_clause_id: int | None
    ai_reason: str | None
    suggestion: str | None
    status: str
    expert_comment: str | None
    confirmed_by: int | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewIssueList(BaseModel):
    items: list[ReviewIssueRead]
    total: int
    page: int
    page_size: int


class ReviewIssueConfirmRequest(BaseModel):
    action: str
    expert_comment: str | None = None
    issue_title: str | None = None
    issue_description: str | None = None
    risk_level: str | None = None
    suggestion: str | None = None
