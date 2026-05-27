from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.standards.schemas import StandardClauseRead, StandardDocumentRead


class ReviewCheckpointCreate(BaseModel):
    checkpoint_code: str | None = None
    checkpoint_name: str
    checkpoint_type: str
    domain: str | None = None
    subdomain: str | None = None
    work_type: str | None = None
    standard_id: int | None = None
    clause_id: int | None = None
    clause_no: str | None = None
    clause_text: str | None = None
    chapter_types: list[str] = []
    target_objects: list[str] = []
    target_parameters: list[str] = []
    keywords: list[str] = []
    check_goal: str | None = None
    check_method: str | None = None
    expected_items: list[str] = []
    forbidden_items: list[str] = []
    parameters: dict = {}
    applicable_condition: dict = {}
    risk_level: str = "major"
    is_mandatory: bool = False
    priority: int = 0
    status: str = "active"


class ReviewCheckpointUpdate(BaseModel):
    checkpoint_code: str | None = None
    checkpoint_name: str | None = None
    checkpoint_type: str | None = None
    domain: str | None = None
    subdomain: str | None = None
    work_type: str | None = None
    standard_id: int | None = None
    clause_id: int | None = None
    clause_no: str | None = None
    clause_text: str | None = None
    chapter_types: list[str] | None = None
    target_objects: list[str] | None = None
    target_parameters: list[str] | None = None
    keywords: list[str] | None = None
    check_goal: str | None = None
    check_method: str | None = None
    expected_items: list[str] | None = None
    forbidden_items: list[str] | None = None
    parameters: dict | None = None
    applicable_condition: dict | None = None
    risk_level: str | None = None
    is_mandatory: bool | None = None
    priority: int | None = None
    status: str | None = None


class ReviewCheckpointRead(BaseModel):
    id: int
    checkpoint_code: str | None
    checkpoint_name: str
    checkpoint_type: str
    domain: str | None
    subdomain: str | None
    work_type: str | None
    standard_id: int | None
    clause_id: int | None
    clause_no: str | None
    clause_text: str | None
    chapter_types: list
    target_objects: list
    target_parameters: list
    keywords: list
    check_goal: str | None
    check_method: str | None
    expected_items: list
    forbidden_items: list
    parameters: dict
    applicable_condition: dict
    risk_level: str
    is_mandatory: bool
    priority: int
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


class GenerateCheckpointsFromClausesResponse(BaseModel):
    created_count: int
    checkpoint_ids: list[int]
    failed: list[dict]
    skipped: list[dict]


class CheckpointGenerationJobRead(BaseModel):
    id: int
    standard_id: int | None
    clause_ids: list
    use_llm: bool
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
