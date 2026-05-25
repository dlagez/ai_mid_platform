from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.review_checkpoints.schemas import (
    GenerateCheckpointsFromClausesRequest,
    GenerateCheckpointsFromClausesResponse,
    ReviewCheckpointCreate,
    ReviewCheckpointList,
    ReviewCheckpointRead,
    ReviewCheckpointUpdate,
)
from app.review_checkpoints.service import ReviewCheckpointService, get_review_checkpoint_service
from app.utils.jwt import CurrentUser, get_current_user
from app.utils.rbac import require_admin

router = APIRouter()


@router.get("", response_model=ReviewCheckpointList)
async def list_review_checkpoints(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    checkpoint_type: str | None = None,
    domain: str | None = None,
    work_type: str | None = None,
    keyword: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> ReviewCheckpointList:
    items, total = service.list_checkpoints(
        db,
        status=status,
        checkpoint_type=checkpoint_type,
        domain=domain,
        work_type=work_type,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ReviewCheckpointList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ReviewCheckpointRead)
async def create_review_checkpoint(
    payload: ReviewCheckpointCreate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewCheckpointRead:
    return service.create_checkpoint(db, payload)


@router.post("/generate-from-standard-clauses", response_model=GenerateCheckpointsFromClausesResponse)
async def generate_review_checkpoints_from_standard_clauses(
    payload: GenerateCheckpointsFromClausesRequest,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
) -> GenerateCheckpointsFromClausesResponse:
    return await service.generate_from_standard_clauses(db, payload)


@router.get("/{checkpoint_id}", response_model=ReviewCheckpointRead)
async def get_review_checkpoint(
    checkpoint_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewCheckpointRead:
    return service.get_checkpoint(db, checkpoint_id)


@router.patch("/{checkpoint_id}", response_model=ReviewCheckpointRead)
async def update_review_checkpoint(
    checkpoint_id: int,
    payload: ReviewCheckpointUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewCheckpointRead:
    return service.update_checkpoint(db, checkpoint_id, payload)


@router.delete("/{checkpoint_id}", response_model=ReviewCheckpointRead)
async def delete_review_checkpoint(
    checkpoint_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewCheckpointRead:
    return service.delete_checkpoint(db, checkpoint_id)
