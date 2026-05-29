from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.chapter_profile.schemas import BuildChapterProfilesResponse
from app.chapter_profile.service import ChapterProfileService, get_chapter_profile_service
from app.checkpoint_executor.schemas import RunCheckpointReviewResponse
from app.checkpoint_executor.service import CheckpointExecutorService, get_checkpoint_executor_service
from app.checkpoint_matcher.schemas import CheckpointMatchListResponse, MatchCheckpointsResponse
from app.checkpoint_matcher.service import CheckpointMatcherService, get_checkpoint_matcher_service
from app.db.session import get_db
from app.review_issues.schemas import ReviewIssueList
from app.review_tasks.schemas import ReviewTaskCreate, ReviewTaskList, ReviewTaskRead, ReviewTaskStartResponse
from app.review_tasks.service import ReviewTaskService, get_review_task_service
from app.utils.jwt import CurrentUser, get_current_user

router = APIRouter()


@router.post("", response_model=ReviewTaskRead)
async def create_review_task(
    payload: ReviewTaskCreate,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTaskService, Depends(get_review_task_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTaskRead:
    return service.create_task(db, payload)


@router.get("", response_model=ReviewTaskList)
async def list_review_tasks(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTaskService, Depends(get_review_task_service)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    plan_document_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> ReviewTaskList:
    items, total = service.list_tasks(
        db,
        status=status,
        plan_document_id=plan_document_id,
        page=page,
        page_size=page_size,
    )
    return ReviewTaskList(items=items, total=total, page=page, page_size=page_size)


@router.get("/{task_id}", response_model=ReviewTaskRead)
async def get_review_task(
    task_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTaskService, Depends(get_review_task_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTaskRead:
    return service.get_task(db, task_id)


@router.post("/{task_id}/start", response_model=ReviewTaskStartResponse)
async def start_review_task(
    task_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTaskService, Depends(get_review_task_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewTaskStartResponse:
    return service.start_task(db, task_id)


@router.get("/{task_id}/issues", response_model=ReviewIssueList)
async def list_review_task_issues(
    task_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewTaskService, Depends(get_review_task_service)],
    db: Annotated[Session, Depends(get_db)],
    version: int | None = Query(None, ge=1),
    status: str | None = None,
    risk_level: str | None = None,
    issue_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> ReviewIssueList:
    items, total = service.list_issues(
        db,
        task_id,
        version=version,
        status=status,
        risk_level=risk_level,
        issue_type=issue_type,
        page=page,
        page_size=page_size,
    )
    return ReviewIssueList(items=items, total=total, page=page, page_size=page_size)


@router.post("/{task_id}/build-chapter-profiles", response_model=BuildChapterProfilesResponse)
async def build_chapter_profiles(
    task_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ChapterProfileService, Depends(get_chapter_profile_service)],
    db: Annotated[Session, Depends(get_db)],
) -> BuildChapterProfilesResponse:
    return await service.build_profiles(db, task_id)


@router.post("/{task_id}/match-checkpoints", response_model=MatchCheckpointsResponse)
async def match_review_checkpoints(
    task_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[CheckpointMatcherService, Depends(get_checkpoint_matcher_service)],
    db: Annotated[Session, Depends(get_db)],
) -> MatchCheckpointsResponse:
    return service.match_task_checkpoints(db, task_id)


@router.get("/{task_id}/checkpoint-matches", response_model=CheckpointMatchListResponse)
async def list_review_checkpoint_matches(
    task_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[CheckpointMatcherService, Depends(get_checkpoint_matcher_service)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    matched_only: bool = False,
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=500),
) -> CheckpointMatchListResponse:
    items, total = service.list_task_matches(
        db,
        task_id,
        status=status,
        matched_only=matched_only,
        page=page,
        page_size=page_size,
    )
    return CheckpointMatchListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{task_id}/run-checkpoint-review", response_model=RunCheckpointReviewResponse)
async def run_checkpoint_review(
    task_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[CheckpointExecutorService, Depends(get_checkpoint_executor_service)],
    db: Annotated[Session, Depends(get_db)],
) -> RunCheckpointReviewResponse:
    return service.run_checkpoint_review(db, task_id)
