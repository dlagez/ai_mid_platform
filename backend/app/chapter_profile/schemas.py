from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterReviewProfileRead(BaseModel):
    id: int
    task_id: int
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
    task_id: int
    created_count: int
    updated_count: int
    failed: list[dict]
    items: list[ChapterReviewProfileRead]
