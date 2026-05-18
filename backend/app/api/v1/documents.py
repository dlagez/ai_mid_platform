from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import PlanDocument, PlanSection
from app.db.session import get_db
from app.services.document_service import DocumentService, get_document_service
from app.utils.exceptions import PlatformError
from app.utils.jwt import CurrentUser, require_permission

router = APIRouter()


class DocumentItem(BaseModel):
    id: int
    file_name: str
    file_path: str
    file_size: int
    parse_status: str
    created_at: str

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    id: int
    file_name: str
    status: str


class SectionItem(BaseModel):
    id: int
    document_id: int
    parent_id: int | None
    level: int
    title: str
    section_no: str | None
    content: str
    sort_no: int
    created_at: str
    children: list["SectionItem"] = Field(default_factory=list)


class DocumentParseResponse(BaseModel):
    id: int
    file_name: str
    parse_status: str
    toc_text: str
    sections: list[SectionItem]


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    current_user: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
) -> DocumentUploadResponse:
    if not (file.filename or "").lower().endswith(".docx"):
        raise PlatformError("Only .docx files are supported.", status_code=400)
    record = await service.upload(db, file, current_user.username)
    background_tasks.add_task(service.parse_in_background, record.id)
    return DocumentUploadResponse(id=record.id, file_name=record.file_name, status=record.parse_status)


@router.get("", response_model=list[DocumentItem])
async def list_documents(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentItem]:
    records = service.list_files(db)
    return [
        DocumentItem(
            id=r.id,
            file_name=r.file_name,
            file_path=r.file_path,
            file_size=r.file_size,
            parse_status=r.parse_status,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in records
    ]


@router.post("/{record_id}/parse", response_model=DocumentParseResponse)
async def parse_document(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentParseResponse:
    record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
    if not record:
        raise PlatformError(f"Document id={record_id} not found", status_code=404)
    record = service.parse(db, record_id)
    sections = service.get_sections(db, record_id)
    return DocumentParseResponse(
        id=record.id,
        file_name=record.file_name,
        parse_status=record.parse_status,
        toc_text=_sections_to_toc_text(sections),
        sections=_build_section_tree(sections),
    )


@router.get("/{record_id}/sections", response_model=DocumentParseResponse)
async def get_document_sections(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentParseResponse:
    record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
    if not record:
        raise PlatformError(f"Document id={record_id} not found", status_code=404)
    sections = service.get_sections(db, record_id)
    return DocumentParseResponse(
        id=record.id,
        file_name=record.file_name,
        parse_status=record.parse_status,
        toc_text=_sections_to_toc_text(sections),
        sections=_build_section_tree(sections),
    )


def _build_section_tree(sections: list[PlanSection]) -> list[SectionItem]:
    items = {
        section.id: SectionItem(
            id=section.id,
            document_id=section.document_id,
            parent_id=section.parent_id,
            level=section.level,
            title=section.title,
            section_no=section.section_no,
            content=section.content,
            sort_no=section.sort_no,
            created_at=section.created_at.isoformat() if section.created_at else "",
        )
        for section in sections
    }

    roots: list[SectionItem] = []
    for section in sections:
        item = items[section.id]
        if section.parent_id and section.parent_id in items:
            items[section.parent_id].children.append(item)
        else:
            roots.append(item)
    return roots


def _sections_to_toc_text(sections: list[PlanSection]) -> str:
    return "\n".join(f"{'  ' * max(section.level - 1, 0)}{section.title}" for section in sections)
