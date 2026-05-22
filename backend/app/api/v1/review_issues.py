from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.review_issues.schemas import ReviewIssueConfirmRequest, ReviewIssueRead
from app.review_issues.service import ReviewIssueService, get_review_issue_service
from app.utils.jwt import CurrentUser, get_current_user

router = APIRouter()


@router.post("/{issue_id}/confirm", response_model=ReviewIssueRead)
async def confirm_review_issue(
    issue_id: int,
    payload: ReviewIssueConfirmRequest,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewIssueService, Depends(get_review_issue_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewIssueRead:
    return service.confirm_issue(db, issue_id, payload)
