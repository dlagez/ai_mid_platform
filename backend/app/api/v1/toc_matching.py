from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import TocMatchItem
from app.db.session import get_db
from app.toc_matcher.schemas import (
    TocMatchCreateRequest,
    TocMatchJobDetail,
    TocMatchJobList,
    TocMatchJobRead,
    TocMatchItemRead,
    TocReviewRequest,
)
from app.toc_matcher.service import TocMatcherService, get_toc_matcher_service
from app.utils.jwt import CurrentUser, get_current_user

router = APIRouter()


@router.post("/jobs", response_model=TocMatchJobDetail)
async def create_toc_match_job(
    payload: TocMatchCreateRequest,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TocMatcherService, Depends(get_toc_matcher_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TocMatchJobDetail:
    job = await service.create_match_job(
        db,
        plan_document_id=payload.plan_document_id,
        standard_id=payload.standard_id,
        section_parse_mode=payload.section_parse_mode,
        model=payload.model,
        created_by=None,
    )
    _, items = service.get_job_detail(db, job.id)
    return TocMatchJobDetail(job=job, items=[_to_item_read(item) for item in items])


@router.get("/jobs", response_model=TocMatchJobList)
async def list_toc_match_jobs(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TocMatcherService, Depends(get_toc_matcher_service)],
    db: Annotated[Session, Depends(get_db)],
    plan_document_id: int | None = None,
    standard_id: int | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> TocMatchJobList:
    items, total = service.list_jobs(
        db,
        plan_document_id=plan_document_id,
        standard_id=standard_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return TocMatchJobList(items=items, total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=TocMatchJobDetail)
async def get_toc_match_job(
    job_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TocMatcherService, Depends(get_toc_matcher_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TocMatchJobDetail:
    job, items = service.get_job_detail(db, job_id)
    return TocMatchJobDetail(job=job, items=[_to_item_read(item) for item in items])


@router.post("/jobs/{job_id}/review", response_model=TocMatchJobDetail)
async def review_toc_match_job(
    job_id: int,
    payload: TocReviewRequest,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TocMatcherService, Depends(get_toc_matcher_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TocMatchJobDetail:
    job = await service.review_job(db, job_id, model=payload.model)
    _, items = service.get_job_detail(db, job.id)
    return TocMatchJobDetail(job=job, items=[_to_item_read(item) for item in items])


@router.post("/items/{item_id}/review", response_model=TocMatchItemRead)
async def review_toc_match_item(
    item_id: int,
    payload: TocReviewRequest,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TocMatcherService, Depends(get_toc_matcher_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TocMatchItemRead:
    item = await service.review_item(db, item_id, model=payload.model)
    return _to_item_read(item)


def _to_item_read(item: TocMatchItem) -> TocMatchItemRead:
    standard = item.standard_section
    plan = item.plan_section
    return TocMatchItemRead(
        id=item.id,
        job_id=item.job_id,
        standard_id=item.standard_id,
        standard_section_id=item.standard_section_id,
        standard_section_no=standard.section_no if standard else None,
        standard_title=standard.title if standard else None,
        standard_path=_section_path(standard) if standard else None,
        plan_document_id=item.plan_document_id,
        plan_section_id=item.plan_section_id,
        plan_section_no=plan.section_no if plan else None,
        plan_title=plan.title if plan else None,
        plan_path=_section_path(plan) if plan else None,
        match_type=item.match_type,
        confidence=float(item.confidence) if item.confidence is not None else None,
        reason=item.reason,
        review_status=item.review_status,
        review_issues=item.review_issues or [],
        raw_review_response=item.raw_review_response,
        review_error=item.review_error,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
    )


def _section_path(section: object) -> str | None:
    title = getattr(section, "title", None)
    parent = getattr(section, "parent", None)
    if not title:
        return None
    if parent and getattr(parent, "title", None):
        return f"{parent.title} / {title}"
    return title
