from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.review_rules.schemas import (
    ReviewRuleCandidateList,
    ReviewRuleCandidateRead,
    ReviewRuleCandidateUpdate,
    ReviewRuleRead,
)
from app.review_rules.service import ReviewRuleService, get_review_rule_service
from app.utils.jwt import CurrentUser, get_current_user
from app.utils.rbac import require_admin

router = APIRouter()


@router.get("/rule-candidates", response_model=ReviewRuleCandidateList)
async def list_rule_candidates(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewRuleService, Depends(get_review_rule_service)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    standard_id: int | None = None,
    rule_type: str | None = None,
    work_type: str | None = None,
    keyword: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> ReviewRuleCandidateList:
    items, total = service.list_candidates(
        db,
        status=status,
        standard_id=standard_id,
        rule_type=rule_type,
        work_type=work_type,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ReviewRuleCandidateList(items=items, total=total, page=page, page_size=page_size)


@router.get("/rule-candidates/{candidate_id}", response_model=ReviewRuleCandidateRead)
async def get_rule_candidate(
    candidate_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewRuleService, Depends(get_review_rule_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewRuleCandidateRead:
    return service.get_candidate(db, candidate_id)


@router.patch("/rule-candidates/{candidate_id}", response_model=ReviewRuleCandidateRead)
async def update_rule_candidate(
    candidate_id: int,
    payload: ReviewRuleCandidateUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewRuleService, Depends(get_review_rule_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewRuleCandidateRead:
    return service.update_candidate(db, candidate_id, payload)


@router.post("/rule-candidates/{candidate_id}/approve", response_model=ReviewRuleRead)
async def approve_rule_candidate(
    candidate_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewRuleService, Depends(get_review_rule_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewRuleRead:
    _, rule = service.approve_candidate(db, candidate_id)
    return rule


@router.post("/rule-candidates/{candidate_id}/reject", response_model=ReviewRuleCandidateRead)
async def reject_rule_candidate(
    candidate_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewRuleService, Depends(get_review_rule_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewRuleCandidateRead:
    return service.reject_candidate(db, candidate_id)
