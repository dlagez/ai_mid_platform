from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    clause_ids: list[int]
    use_llm: bool = True


class GenerateCheckpointsFromClausesResponse(BaseModel):
    created_count: int
    checkpoint_ids: list[int]
    failed: list[dict]
    skipped: list[dict]
