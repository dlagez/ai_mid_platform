from __future__ import annotations

from pydantic import BaseModel


class RunCheckpointReviewResponse(BaseModel):
    task_id: int
    executed_count: int
    skipped_count: int
    failed: list[dict]
