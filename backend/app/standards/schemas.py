from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class StandardDocumentCreate(BaseModel):
    standard_code: str | None = None
    standard_name: str
    standard_type: str | None = None
    version: str | None = None
    effective_date: date | None = None
    source_file_id: int | None = None
    source_document_id: int | None = None
    status: str = "draft"
    description: str | None = None


class StandardDocumentUpdate(BaseModel):
    standard_code: str | None = None
    standard_name: str | None = None
    standard_type: str | None = None
    version: str | None = None
    effective_date: date | None = None
    source_file_id: int | None = None
    source_document_id: int | None = None
    status: str | None = None
    description: str | None = None


class StandardDocumentRead(BaseModel):
    id: int
    standard_code: str | None
    standard_name: str
    standard_type: str | None
    version: str | None
    effective_date: date | None
    source_file_id: int | None
    source_document_id: int | None
    status: str
    description: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StandardDocumentList(BaseModel):
    items: list[StandardDocumentRead]
    total: int


class ImportStandardFromDocumentRequest(BaseModel):
    document_id: int | None = None
    standard_code: str | None = None
    standard_name: str
    standard_type: str | None = None
    version: str | None = None
    effective_date: date | None = None
    description: str | None = None


class ImportStandardFromDocumentResponse(BaseModel):
    standard_id: int
    clause_count: int


class StandardClauseCreate(BaseModel):
    parent_id: int | None = None
    chapter_no: str | None = None
    clause_no: str | None = None
    title: str | None = None
    content: str
    level: int = 1
    path: str | None = None
    is_mandatory: bool = False
    keywords: list[str] = Field(default_factory=list)
    applicable_work_types: list[str] = Field(default_factory=list)
    source_section_id: int | None = None
    order_no: int = 0
    embedding_id: str | None = None


class StandardClauseUpdate(BaseModel):
    parent_id: int | None = None
    chapter_no: str | None = None
    clause_no: str | None = None
    title: str | None = None
    content: str | None = None
    level: int | None = None
    path: str | None = None
    is_mandatory: bool | None = None
    keywords: list[str] | None = None
    applicable_work_types: list[str] | None = None
    order_no: int | None = None
    embedding_id: str | None = None


class StandardClauseRead(BaseModel):
    id: int
    standard_id: int
    parent_id: int | None
    chapter_no: str | None
    clause_no: str | None
    title: str | None
    content: str
    level: int
    path: str | None
    is_mandatory: bool
    keywords: list
    applicable_work_types: list
    source_section_id: int | None
    order_no: int
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StandardClauseList(BaseModel):
    items: list[StandardClauseRead]
    total: int
    page: int
    page_size: int
