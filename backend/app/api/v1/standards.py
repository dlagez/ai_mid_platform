from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.standards.schemas import (
    ImportStandardFromDocumentRequest,
    ImportStandardFromDocumentResponse,
    StandardClauseCreate,
    StandardClauseList,
    StandardClauseRead,
    StandardClauseUpdate,
    StandardDocumentCreate,
    StandardDocumentList,
    StandardDocumentRead,
    StandardDocumentUpdate,
)
from app.standards.service import StandardService, get_standard_service
from app.utils.jwt import CurrentUser, get_current_user
from app.utils.rbac import require_admin

router = APIRouter()
clauses_router = APIRouter()


@router.get("", response_model=StandardDocumentList)
async def list_standards(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardDocumentList:
    items, total = service.list_standards(db)
    return StandardDocumentList(items=items, total=total)


@router.post("", response_model=StandardDocumentRead)
async def create_standard(
    payload: StandardDocumentCreate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardDocumentRead:
    return service.create_standard(db, payload)


@router.post("/import-from-document", response_model=ImportStandardFromDocumentResponse)
async def import_standard_from_document(
    payload: ImportStandardFromDocumentRequest,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ImportStandardFromDocumentResponse:
    standard, count = service.import_from_document(db, payload)
    return ImportStandardFromDocumentResponse(standard_id=standard.id, clause_count=count)


@router.get("/{standard_id}", response_model=StandardDocumentRead)
async def get_standard(
    standard_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardDocumentRead:
    return service.get_standard(db, standard_id)


@router.patch("/{standard_id}", response_model=StandardDocumentRead)
async def update_standard(
    standard_id: int,
    payload: StandardDocumentUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardDocumentRead:
    return service.update_standard(db, standard_id, payload)


@router.delete("/{standard_id}", response_model=StandardDocumentRead)
async def delete_standard(
    standard_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardDocumentRead:
    return service.archive_standard(db, standard_id)


@router.get("/{standard_id}/clauses", response_model=StandardClauseList)
async def list_standard_clauses(
    standard_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
    keyword: str | None = None,
    clause_no: str | None = None,
    is_mandatory: bool | None = None,
    work_type: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> StandardClauseList:
    items, total = service.list_clauses(
        db,
        standard_id,
        keyword=keyword,
        clause_no=clause_no,
        is_mandatory=is_mandatory,
        work_type=work_type,
        page=page,
        page_size=page_size,
    )
    return StandardClauseList(items=items, total=total, page=page, page_size=page_size)


@router.post("/{standard_id}/clauses", response_model=StandardClauseRead)
async def create_standard_clause(
    standard_id: int,
    payload: StandardClauseCreate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardClauseRead:
    return service.create_clause(db, standard_id, payload)


@router.get("/clauses/{clause_id}", response_model=StandardClauseRead)
async def get_standard_clause(
    clause_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardClauseRead:
    return service.get_clause(db, clause_id)


@router.patch("/clauses/{clause_id}", response_model=StandardClauseRead)
async def update_standard_clause(
    clause_id: int,
    payload: StandardClauseUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardClauseRead:
    return service.update_clause(db, clause_id, payload)


@router.delete("/clauses/{clause_id}", response_model=StandardClauseRead)
async def delete_standard_clause(
    clause_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardClauseRead:
    return service.delete_clause(db, clause_id)


@clauses_router.get("/{clause_id}", response_model=StandardClauseRead)
async def get_standard_clause_alias(
    clause_id: int,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardClauseRead:
    return service.get_clause(db, clause_id)


@clauses_router.patch("/{clause_id}", response_model=StandardClauseRead)
async def update_standard_clause_alias(
    clause_id: int,
    payload: StandardClauseUpdate,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardClauseRead:
    return service.update_clause(db, clause_id, payload)


@clauses_router.delete("/{clause_id}", response_model=StandardClauseRead)
async def delete_standard_clause_alias(
    clause_id: int,
    _: Annotated[CurrentUser, Depends(require_admin)],
    service: Annotated[StandardService, Depends(get_standard_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StandardClauseRead:
    return service.delete_clause(db, clause_id)
