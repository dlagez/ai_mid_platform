from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import DocumentRecord
from app.db.session import get_db
from app.services.document_service import DocumentService, get_document_service
from app.utils.exceptions import PlatformError
from app.utils.jwt import CurrentUser, require_permission

router = APIRouter()


class DocumentItem(BaseModel):
    id: int
    file_name: str
    minio_path: str
    uploaded_by: str
    uploaded_at: str

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    id: int
    file_name: str
    status: str


class DocumentParseResponse(BaseModel):
    id: int
    file_name: str
    toc_text: str


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    current_user: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> DocumentUploadResponse:
    record = await service.upload(db, file, current_user.username)
    return DocumentUploadResponse(id=record.id, file_name=record.file_name, status="uploaded")


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
            minio_path=r.minio_path,
            uploaded_by=r.uploaded_by,
            uploaded_at=r.uploaded_at.isoformat() if r.uploaded_at else "",
        )
        for r in records
    ]


@router.post("/{record_id}/parse", response_model=DocumentParseResponse)
async def parse_document(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentParseResponse:
    record = db.query(DocumentRecord).filter(DocumentRecord.id == record_id).first()
    if not record:
        raise PlatformError(f"Document id={record_id} not found", status_code=404)
    toc_text = service.parse(db, record_id)
    return DocumentParseResponse(
        id=record.id,
        file_name=record.file_name,
        toc_text=toc_text,
    )
