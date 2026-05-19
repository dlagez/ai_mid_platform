from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import UtilityParseRecord
from app.db.session import get_db
from app.parsers.factory import ParserConfigError, ParserUnsupportedFileError
from app.parsers.ppocr import PPOcrParseError
from app.services.utility_parse_service import UtilityParseService, get_utility_parse_service
from app.utils.exceptions import PlatformError
from app.utils.jwt import CurrentUser, require_permission

router = APIRouter()

SUPPORTED_PPOCR_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")


class UtilityParseRecordItem(BaseModel):
    id: int
    source_file_name: str
    source_file_path: str
    source_file_size: int
    source_content_type: str | None
    parsed_file_name: str | None
    parsed_file_path: str | None
    parsed_file_size: int | None
    parser_provider: str
    parse_status: str
    parsed: bool
    error_message: str | None
    created_by: str
    created_at: str
    completed_at: str | None


class PPOcrParseResponse(BaseModel):
    record: UtilityParseRecordItem
    markdown: str


@router.post("/ppocr/parse", response_model=PPOcrParseResponse)
async def parse_ppocr_file(
    current_user: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[UtilityParseService, Depends(get_utility_parse_service)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> PPOcrParseResponse:
    if not (file.filename or "").lower().endswith(SUPPORTED_PPOCR_EXTENSIONS):
        raise PlatformError("Only PDF and image files are supported by PPOCR.", status_code=400)
    try:
        record = await service.parse_ppocr(db, file, current_user.username)
        markdown = service.get_markdown(record)
        return PPOcrParseResponse(record=_to_record_item(record), markdown=markdown)
    except (ParserConfigError, ParserUnsupportedFileError, PPOcrParseError) as exc:
        raise PlatformError(str(exc), status_code=400) from exc


@router.get("/ppocr/records", response_model=list[UtilityParseRecordItem])
async def list_ppocr_records(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[UtilityParseService, Depends(get_utility_parse_service)],
    db: Annotated[Session, Depends(get_db)],
) -> list[UtilityParseRecordItem]:
    return [_to_record_item(record) for record in service.list_ppocr_records(db)]


@router.get("/ppocr/records/{record_id}/markdown", response_model=PPOcrParseResponse)
async def get_ppocr_markdown(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[UtilityParseService, Depends(get_utility_parse_service)],
    db: Annotated[Session, Depends(get_db)],
) -> PPOcrParseResponse:
    record = service.get_record(db, record_id)
    if not record or record.parser_provider != "ppocr":
        raise PlatformError(f"PPOCR record id={record_id} not found", status_code=404)
    return PPOcrParseResponse(record=_to_record_item(record), markdown=service.get_markdown(record))


def _to_record_item(record: UtilityParseRecord) -> UtilityParseRecordItem:
    return UtilityParseRecordItem(
        id=record.id,
        source_file_name=record.source_file_name,
        source_file_path=record.source_file_path,
        source_file_size=record.source_file_size,
        source_content_type=record.source_content_type,
        parsed_file_name=record.parsed_file_name,
        parsed_file_path=record.parsed_file_path,
        parsed_file_size=record.parsed_file_size,
        parser_provider=record.parser_provider,
        parse_status=record.parse_status,
        parsed=record.parsed,
        error_message=record.error_message,
        created_by=record.created_by,
        created_at=record.created_at.isoformat() if record.created_at else "",
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
    )
