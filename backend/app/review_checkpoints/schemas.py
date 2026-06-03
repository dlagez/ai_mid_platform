from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.standards.schemas import StandardClauseRead, StandardDocumentRead


class ReviewCheckpointCreate(BaseModel):
    rule_code: str | None = None
    rule_text: str
    object_terms: list[str] = []
    standard_id: int | None = None
    clause_id: int | None = None
    clause_no: str | None = None
    clause_text: str | None = None
    confidence: float | None = None
    status: str = "active"


class ReviewCheckpointUpdate(BaseModel):
    rule_code: str | None = None
    rule_text: str | None = None
    object_terms: list[str] | None = None
    standard_id: int | None = None
    clause_id: int | None = None
    clause_no: str | None = None
    clause_text: str | None = None
    confidence: float | None = None
    status: str | None = None


class ReviewCheckpointRead(BaseModel):
    id: int
    rule_code: str | None
    rule_text: str
    object_terms: list
    standard_id: int | None
    clause_id: int | None
    clause_no: str | None
    clause_text: str | None
    confidence: float | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewCheckpointList(BaseModel):
    items: list[ReviewCheckpointRead]
    total: int
    page: int
    page_size: int


class GenerateCheckpointsFromClausesRequest(BaseModel):
    standard_id: int | None = None
    clause_ids: list[int]
    use_llm: bool = True
    concurrency: int = Field(default=5, ge=1, le=10)


class GenerateCheckpointsFromClausesResponse(BaseModel):
    created_count: int
    checkpoint_ids: list[int]
    failed: list[dict]
    skipped: list[dict]


class ManualCheckpointImportRequest(BaseModel):
    standard_id: int
    clause_id: int
    payload: dict | list


class ManualCheckpointImportResponse(BaseModel):
    created_count: int
    checkpoint_ids: list[int]


class CheckpointGenerationJobRead(BaseModel):
    id: int
    standard_id: int | None
    clause_ids: list
    use_llm: bool
    concurrency: int
    status: str
    total_clauses: int
    processed_clauses: int
    created_count: int
    failed_count: int
    skipped_count: int
    checkpoint_ids: list
    failed: list
    skipped: list
    celery_task_id: str | None
    error_message: str | None
    created_by: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckpointGenerationJobList(BaseModel):
    items: list[CheckpointGenerationJobRead]
    total: int
    page: int
    page_size: int


class CheckpointGenerationItemRead(BaseModel):
    id: int
    job_id: int
    standard_id: int | None
    clause_id: int | None
    clause_no: str | None
    clause_title: str | None
    status: str
    checkpoint_ids: list
    created_count: int
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckpointGenerationItemList(BaseModel):
    items: list[CheckpointGenerationItemRead]
    total: int
    page: int
    page_size: int


class CheckpointGenerationJobCreateResponse(BaseModel):
    job: CheckpointGenerationJobRead


class CheckpointGenerationTreeResponse(BaseModel):
    job: CheckpointGenerationJobRead
    standard: StandardDocumentRead | None
    clauses: list[StandardClauseRead]
    items: list[CheckpointGenerationItemRead]
    checkpoints: list[ReviewCheckpointRead]


class ReviewCheckpointTreeResponse(BaseModel):
    standard: StandardDocumentRead
    clauses: list[StandardClauseRead]
    checkpoints: list[ReviewCheckpointRead]
