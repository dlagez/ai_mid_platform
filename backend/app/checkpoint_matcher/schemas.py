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


class CheckpointMatchWithCheckpointRead(CheckpointMatchResultRead):
    checkpoint: ReviewCheckpointRead | None = None


class CheckpointMatchListResponse(BaseModel):
    items: list[CheckpointMatchWithCheckpointRead]
    total: int
