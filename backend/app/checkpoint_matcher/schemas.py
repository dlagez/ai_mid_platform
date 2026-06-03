from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.review_checkpoints.schemas import ReviewCheckpointRead


class CheckpointMatchResultRead(BaseModel):
    id: int
    task_id: int
    section_id: int
    checkpoint_id: int
    match_score: float
    match_reason: str | None
    match_dimensions: dict
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchCheckpointsResponse(BaseModel):
    task_id: int
    selected_count: int
    candidate_count: int
    items: list[CheckpointMatchResultRead]


class PlanSectionSummaryRead(BaseModel):
    id: int
    level: int
    title: str
    section_no: str | None = None
    content: str = ""

    model_config = ConfigDict(from_attributes=True)


class ChapterProfileMatchRead(BaseModel):
    object_terms: list = []
    chapter_title: str | None = None
    chapter_path: str | None = None
    evidence_text: str | None = None
    source_text: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CheckpointMatchWithCheckpointRead(CheckpointMatchResultRead):
    checkpoint: ReviewCheckpointRead | None = None
    section: PlanSectionSummaryRead | None = None
    profile: ChapterProfileMatchRead | None = None


class CheckpointMatchListResponse(BaseModel):
    items: list[CheckpointMatchWithCheckpointRead]
    total: int
    page: int | None = None
    page_size: int | None = None
