from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewTaskCreate(BaseModel):
    task_name: str | None = None
    plan_document_id: int
    template_id: int | None = None
    work_type: str | None = None
    review_mode: str = "standard"


class ReviewTaskUpdate(BaseModel):
    task_name: str | None = None
    template_id: int | None = None
    work_type: str | None = None
    review_mode: str | None = None
    status: str | None = None


class ReviewTaskRead(BaseModel):
    id: int
    task_name: str | None
    plan_document_id: int
    template_id: int | None
    work_type: str | None
    review_mode: str
    status: str
    version: int
    progress: int
    total_issue_count: int
    critical_issue_count: int
    major_issue_count: int
    minor_issue_count: int
    created_by: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskList(BaseModel):
    items: list[ReviewTaskRead]
    total: int
    page: int
    page_size: int


class ReviewTaskStartResponse(BaseModel):
    id: int
    status: str
    version: int | None = None
    total_issue_count: int | None = None
    critical_issue_count: int | None = None
    major_issue_count: int | None = None
    minor_issue_count: int | None = None
