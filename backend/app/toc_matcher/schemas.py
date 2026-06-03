from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TocMatchCreateRequest(BaseModel):
    plan_document_id: int
    standard_id: int
    section_parse_mode: str | None = None
    model: str | None = None


class TocMatchJobRead(BaseModel):
    id: int
    plan_document_id: int
    plan_parse_result_id: int | None
    standard_id: int
    model: str | None
    status: str
    match_count: int
    raw_llm_response: Any = None
    error_message: str | None
    created_by: int | None
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TocMatchItemRead(BaseModel):
    id: int
    job_id: int
    standard_id: int
    standard_clause_id: int
    standard_clause_no: str | None = None
    standard_title: str | None = None
    standard_path: str | None = None
    plan_document_id: int
    plan_section_id: int
    plan_section_no: str | None = None
    plan_title: str | None = None
    plan_path: str | None = None
    match_type: str
    confidence: float | None
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TocMatchJobDetail(BaseModel):
    job: TocMatchJobRead
    items: list[TocMatchItemRead] = Field(default_factory=list)


class TocMatchJobList(BaseModel):
    items: list[TocMatchJobRead]
    total: int
    page: int
    page_size: int
