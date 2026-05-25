from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewIssueEvidenceRead(BaseModel):
    id: int
    issue_id: int
    evidence_type: str | None
    standard_id: int | None
    clause_id: int | None
    clause_no: str | None
    clause_text: str | None
    plan_section_id: int | None
    plan_text: str | None
    checkpoint_id: int | None
    match_reason: str | None
    score: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

