from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.review_templates.schemas import (
    ImportTemplateFromDocumentRequest,
    ImportTemplateFromDocumentResponse,
    ReviewTemplateCreate,
    ReviewTemplateList,
    ReviewTemplateRead,
    ReviewTemplateUpdate,
    TemplateSectionRuleCreate,
    TemplateSectionRuleList,
    TemplateSectionRuleRead,
    TemplateSectionRuleTreeItem,
    TemplateSectionRuleUpdate,
)
from app.review_templates.service import (
    ReviewTemplateService,
    get_review_template_service,
    template_section_rules_to_tree,
)
from app.utils.jwt import CurrentUser, get_current_user
from app.utils.rbac import require_admin

router = APIRouter()
section_rules_router = APIRouter()


@router.get("", response_model=ReviewTemplateList)
async def list_review_templates(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTemplateList:
    items, total = service.list_templates(db)
    return ReviewTemplateList(items=items, total=total)


@router.post("", response_model=ReviewTemplateRead)
async def create_review_template(
    payload: ReviewTemplateCreate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTemplateRead:
    return service.create_template(db, payload)


@router.post("/import-from-document", response_model=ImportTemplateFromDocumentResponse)
async def import_review_template_from_document(
    payload: ImportTemplateFromDocumentRequest,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ImportTemplateFromDocumentResponse:
    template, count = service.import_from_document(db, payload)
    return ImportTemplateFromDocumentResponse(template_id=template.id, section_rule_count=count)


@router.get("/{template_id}", response_model=ReviewTemplateRead)
async def get_review_template(
    template_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTemplateRead:
    return service.get_template(db, template_id)


@router.patch("/{template_id}", response_model=ReviewTemplateRead)
async def update_review_template(
    template_id: int,
    payload: ReviewTemplateUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTemplateRead:
    return service.update_template(db, template_id, payload)


@router.delete("/{template_id}", response_model=ReviewTemplateRead)
async def delete_review_template(
    template_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTemplateRead:
    return service.archive_template(db, template_id)


@router.get("/{template_id}/section-rules", response_model=TemplateSectionRuleList)
async def list_template_section_rules(
    template_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateSectionRuleList:
    rules = service.list_section_rules(db, template_id)
    return TemplateSectionRuleList(
        items=[TemplateSectionRuleTreeItem(**item) for item in template_section_rules_to_tree(rules)],
        flat_items=rules,
    )


@router.post("/{template_id}/section-rules", response_model=TemplateSectionRuleRead)
async def create_template_section_rule(
    template_id: int,
    payload: TemplateSectionRuleCreate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateSectionRuleRead:
    return service.create_section_rule(db, template_id, payload)


@router.post("/{template_id}/activate", response_model=ReviewTemplateRead)
async def activate_review_template(
    template_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTemplateRead:
    return service.activate_template(db, template_id)


@router.post("/{template_id}/disable", response_model=ReviewTemplateRead)
async def disable_review_template(
    template_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTemplateRead:
    return service.disable_template(db, template_id)


@router.patch("/section-rules/{rule_id}", response_model=TemplateSectionRuleRead)
async def update_template_section_rule(
    rule_id: int,
    payload: TemplateSectionRuleUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateSectionRuleRead:
    return service.update_section_rule(db, rule_id, payload)


@router.delete("/section-rules/{rule_id}", response_model=TemplateSectionRuleRead)
async def delete_template_section_rule(
    rule_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateSectionRuleRead:
    return service.delete_section_rule(db, rule_id)


@section_rules_router.patch("/{rule_id}", response_model=TemplateSectionRuleRead)
async def update_template_section_rule_alias(
    rule_id: int,
    payload: TemplateSectionRuleUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateSectionRuleRead:
    return service.update_section_rule(db, rule_id, payload)


@section_rules_router.delete("/{rule_id}", response_model=TemplateSectionRuleRead)
async def delete_template_section_rule_alias(
    rule_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewTemplateService, Depends(get_review_template_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateSectionRuleRead:
    return service.delete_section_rule(db, rule_id)
