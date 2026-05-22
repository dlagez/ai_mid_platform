from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewTemplateCreate(BaseModel):
    name: str
    code: str | None = None
    work_type: str | None = None
    source_document_id: int | None = None
    description: str | None = None
    version: str = "v1.0"
    status: str = "draft"


class ReviewTemplateUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    work_type: str | None = None
    source_document_id: int | None = None
    description: str | None = None
    version: str | None = None
    status: str | None = None


class ReviewTemplateRead(BaseModel):
    id: int
    name: str
    code: str | None
    work_type: str | None
    source_document_id: int | None
    description: str | None
    version: str
    status: str
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewTemplateList(BaseModel):
    items: list[ReviewTemplateRead]
    total: int


class ImportTemplateFromDocumentRequest(BaseModel):
    document_id: int
    name: str | None = None
    code: str | None = None
    work_type: str | None = None
    description: str | None = None


class ImportTemplateFromDocumentResponse(BaseModel):
    template_id: int
    section_rule_count: int


class TemplateSectionRuleCreate(BaseModel):
    parent_id: int | None = None
    section_code: str | None = None
    standard_title: str
    level: int
    order_no: int = 0
    required: bool = True
    aliases: list[str] = Field(default_factory=list)
    required_points: list[str] = Field(default_factory=list)
    min_word_count: int = 0
    risk_level: str = "major"
    match_strategy: str = "title_semantic"
    enabled: bool = True


class TemplateSectionRuleUpdate(BaseModel):
    parent_id: int | None = None
    section_code: str | None = None
    standard_title: str | None = None
    level: int | None = None
    order_no: int | None = None
    required: bool | None = None
    aliases: list[str] | None = None
    required_points: list[str] | None = None
    min_word_count: int | None = None
    risk_level: str | None = None
    match_strategy: str | None = None
    enabled: bool | None = None


class TemplateSectionRuleRead(BaseModel):
    id: int
    template_id: int
    parent_id: int | None
    section_code: str | None
    standard_title: str
    level: int
    order_no: int
    required: bool
    aliases: list
    required_points: list
    min_word_count: int
    risk_level: str
    match_strategy: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateSectionRuleTreeItem(TemplateSectionRuleRead):
    children: list["TemplateSectionRuleTreeItem"] = Field(default_factory=list)


class TemplateSectionRuleList(BaseModel):
    items: list[TemplateSectionRuleTreeItem]
    flat_items: list[TemplateSectionRuleRead]


TemplateSectionRuleTreeItem.model_rebuild()
