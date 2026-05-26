from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterReviewProfileRead(BaseModel):
    id: int
    task_id: int | None
    document_id: int
    section_id: int
    chapter_title: str | None
    chapter_path: str | None
    chapter_type: str | None
    main_domain: str | None
    subdomains: list
    construction_objects: list
    materials: list
    mentioned_parameters: list
    mentioned_methods: list
    mentioned_risks: list
    mentioned_standards: list
    expected_missing_objects: list
    summary: str | None
    confidence: float | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BuildChapterProfilesResponse(BaseModel):
    task_id: int | None
    document_id: int
    created_count: int
    updated_count: int
    failed: list[dict]
    items: list[ChapterReviewProfileRead]


class ChapterReviewProfileList(BaseModel):
    items: list[ChapterReviewProfileRead]
    total: int
    page: int
    page_size: int


class ChapterProfileGenerationJobRead(BaseModel):
    id: int
    document_id: int
    task_id: int | None
    status: str
    total_sections: int
    processed_sections: int
    created_count: int
    updated_count: int
    failed_count: int
    rule_only_count: int
    celery_task_id: str | None
    error_message: str | None
    created_by: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChapterProfileGenerationJobList(BaseModel):
    items: list[ChapterProfileGenerationJobRead]
    total: int
    page: int
    page_size: int


class ChapterProfileGenerationItemRead(BaseModel):
    id: int
    job_id: int
    document_id: int
    section_id: int | None
    section_title: str | None
    section_path: str | None
    status: str
    profile_id: int | None
    used_llm: bool
    confidence: float | None
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChapterProfileGenerationItemList(BaseModel):
    items: list[ChapterProfileGenerationItemRead]
    total: int
    page: int
    page_size: int


class CreateChapterProfileGenerationJobResponse(BaseModel):
    job: ChapterProfileGenerationJobRead
