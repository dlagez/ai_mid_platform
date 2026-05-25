from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.review_checkpoints.schemas import (
    CheckpointGenerationItemList,
    CheckpointGenerationJobCreateResponse,
    CheckpointGenerationJobList,
    CheckpointGenerationJobRead,
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


@router.post("/generation-jobs", response_model=CheckpointGenerationJobCreateResponse)
async def create_review_checkpoint_generation_job(
    payload: GenerateCheckpointsFromClausesRequest,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
) -> CheckpointGenerationJobCreateResponse:
    job = service.create_generation_job(db, payload)
    return CheckpointGenerationJobCreateResponse(job=job)


@router.get("/generation-jobs", response_model=CheckpointGenerationJobList)
async def list_review_checkpoint_generation_jobs(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
    standard_id: int | None = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> CheckpointGenerationJobList:
    items, total = service.list_generation_jobs(
        db,
        standard_id=standard_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return CheckpointGenerationJobList(items=items, total=total, page=page, page_size=page_size)


@router.get("/generation-jobs/{job_id}", response_model=CheckpointGenerationJobRead)
async def get_review_checkpoint_generation_job(
    job_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
) -> CheckpointGenerationJobRead:
    return service.get_generation_job(db, job_id)


@router.get("/generation-jobs/{job_id}/items", response_model=CheckpointGenerationItemList)
async def list_review_checkpoint_generation_items(
    job_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> CheckpointGenerationItemList:
    service.get_generation_job(db, job_id)
    items, total = service.list_generation_items(db, job_id=job_id, status=status, page=page, page_size=page_size)
    return CheckpointGenerationItemList(items=items, total=total, page=page, page_size=page_size)


@router.get("/generation-items", response_model=CheckpointGenerationItemList)
async def list_review_checkpoint_generation_items_global(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReviewCheckpointService, Depends(get_review_checkpoint_service)],
    db: Annotated[Session, Depends(get_db)],
    standard_id: int | None = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> CheckpointGenerationItemList:
    items, total = service.list_generation_items(
        db,
        standard_id=standard_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return CheckpointGenerationItemList(items=items, total=total, page=page, page_size=page_size)


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
