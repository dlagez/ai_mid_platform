from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import UtilityParseRecord
from app.db.session import get_db
from app.parsers.factory import ParserConfigError, ParserUnsupportedFileError
from app.parsers.ppocr import PPOcrParseError
from app.parsers.section_strategy import SECTION_REBUILD_STRATEGIES, parse_custom_patterns
from app.services.ppocr_pdf_service import (
    PPOcrPdfService,
    get_ppocr_pdf_service,
    markdown_map_to_dict,
    parse_job_to_dict,
    parse_page_to_dict,
    parse_section_to_dict,
)
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


class ParseJobItem(BaseModel):
    id: int
    file_id: str
    file_name: str
    file_size: int
    file_hash: str
    page_count: int
    source_file_path: str
    parser_provider: str
    parse_mode: str
    ocr_endpoint: str
    status: str
    dpi: int
    batch_size: int
    page_timeout_seconds: int
    min_confidence: float
    low_confidence_flag: bool
    total_pages: int
    succeeded_pages: int
    failed_pages: int
    low_confidence_pages: int
    avg_confidence: float | None
    block_count: int
    metadata: dict[str, Any]
    error_message: str | None
    result_markdown_path: str | None
    result_json_path: str | None
    raw_result_path: str | None
    created_by: str
    created_at: str | None
    started_at: str | None
    completed_at: str | None


class ParsePageItem(BaseModel):
    id: int
    job_id: int
    page_no: int
    status: str
    image_path: str | None
    raw_json_path: str | None
    text: str
    markdown_content: str
    rec_texts: list[Any]
    rec_scores: list[Any]
    rec_polys: list[Any]
    average_confidence: float | None
    min_confidence: float | None
    block_count: int
    low_confidence_flag: bool
    retry_count: int
    error_message: str | None
    started_at: str | None
    completed_at: str | None


class MarkdownMapItem(BaseModel):
    id: int
    job_id: int
    page_result_id: int
    page_no: int
    markdown_start: int
    markdown_end: int
    anchor: str
    block_count: int
    created_at: str | None


class ParseJobDetail(BaseModel):
    job: ParseJobItem
    pages: list[ParsePageItem]
    markdown_maps: list[MarkdownMapItem] = []


class ParseJobMarkdownResponse(BaseModel):
    job: ParseJobItem
    markdown: str
    markdown_maps: list[MarkdownMapItem]


class ParseResultSectionFlatItem(BaseModel):
    id: int
    document_id: int
    job_id: int
    parent_id: int | None
    title_level: int
    title: str
    section_no: str | None
    content: str
    sort_no: int
    created_at: str | None


class ParseResultSectionItem(ParseResultSectionFlatItem):
    children: list["ParseResultSectionItem"] = Field(default_factory=list)


class ParseJobSectionsResponse(BaseModel):
    job: ParseJobItem
    sections: list[ParseResultSectionItem]
    flat_sections: list[ParseResultSectionFlatItem]


ParseResultSectionItem.model_rebuild()


class SectionRebuildRequest(BaseModel):
    strategy: str = "decimal_number"
    use_toc_outline: bool = True
    level1_pattern: str | None = None
    level2_pattern: str | None = None
    level3_pattern: str | None = None


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


@router.post("/ppocr/pdf/jobs", response_model=ParseJobItem)
async def create_ppocr_pdf_job(
    current_user: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> ParseJobItem:
    try:
        job = await service.create_pdf_job(db, file, current_user.username)
        return ParseJobItem(**parse_job_to_dict(job))
    except ValueError as exc:
        raise PlatformError(str(exc), status_code=400) from exc


@router.get("/ppocr/pdf/jobs", response_model=list[ParseJobItem])
async def list_ppocr_pdf_jobs(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ParseJobItem]:
    return [ParseJobItem(**parse_job_to_dict(job)) for job in service.list_jobs(db)]


@router.get("/ppocr/pdf/jobs/{job_id}", response_model=ParseJobDetail)
async def get_ppocr_pdf_job(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ParseJobDetail:
    job = service.get_job(db, job_id)
    if not job:
        raise PlatformError(f"Parse job id={job_id} not found", status_code=404)
    maps = service.get_markdown_maps(db, job_id)
    return ParseJobDetail(
        job=ParseJobItem(**parse_job_to_dict(job)),
        pages=[ParsePageItem(**parse_page_to_dict(page)) for page in sorted(job.pages, key=lambda item: item.page_no)],
        markdown_maps=[MarkdownMapItem(**markdown_map_to_dict(item)) for item in maps],
    )


@router.get("/ppocr/pdf/jobs/{job_id}/markdown", response_model=ParseJobMarkdownResponse)
async def get_ppocr_pdf_markdown(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ParseJobMarkdownResponse:
    job = service.get_job(db, job_id)
    if not job:
        raise PlatformError(f"Parse job id={job_id} not found", status_code=404)
    maps = service.get_markdown_maps(db, job_id)
    return ParseJobMarkdownResponse(
        job=ParseJobItem(**parse_job_to_dict(job)),
        markdown=service.get_markdown(job),
        markdown_maps=[MarkdownMapItem(**markdown_map_to_dict(item)) for item in maps],
    )


@router.get("/ppocr/pdf/jobs/{job_id}/sections", response_model=ParseJobSectionsResponse)
async def get_ppocr_pdf_sections(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ParseJobSectionsResponse:
    job = service.get_job(db, job_id)
    if not job:
        raise PlatformError(f"Parse job id={job_id} not found", status_code=404)
    flat_sections = service.get_sections(db, job_id)
    return ParseJobSectionsResponse(
        job=ParseJobItem(**parse_job_to_dict(job)),
        sections=[ParseResultSectionItem(**item) for item in service.get_section_tree(db, job_id)],
        flat_sections=[ParseResultSectionFlatItem(**parse_section_to_dict(item)) for item in flat_sections],
    )


@router.post("/ppocr/pdf/jobs/{job_id}/sections/rebuild", response_model=ParseJobSectionsResponse)
async def rebuild_ppocr_pdf_sections(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
    request: Annotated[SectionRebuildRequest, Body()] = SectionRebuildRequest(),
) -> ParseJobSectionsResponse:
    try:
        strategy = request.strategy.strip().lower()
        if strategy not in SECTION_REBUILD_STRATEGIES:
            supported = ", ".join(sorted(SECTION_REBUILD_STRATEGIES))
            raise ValueError(f"Unsupported section rebuild strategy: {strategy}. Supported: {supported}.")
        custom_patterns = parse_custom_patterns(request.model_dump()) if strategy == "custom" else None
        flat_sections = service.rebuild_sections(
            db,
            job_id,
            strategy=strategy,
            custom_patterns=custom_patterns,
            use_toc_outline=request.use_toc_outline,
        )
    except FileNotFoundError as exc:
        raise PlatformError(str(exc), status_code=404) from exc
    except ValueError as exc:
        raise PlatformError(str(exc), status_code=400) from exc
    job = service.get_job(db, job_id)
    if not job:
        raise PlatformError(f"Parse job id={job_id} not found", status_code=404)
    return ParseJobSectionsResponse(
        job=ParseJobItem(**parse_job_to_dict(job)),
        sections=[ParseResultSectionItem(**item) for item in service.get_section_tree(db, job_id)],
        flat_sections=[ParseResultSectionFlatItem(**parse_section_to_dict(item)) for item in flat_sections],
    )


@router.get("/ppocr/pdf/jobs/{job_id}/source")
async def preview_ppocr_pdf_source(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    job = service.get_job(db, job_id)
    if not job:
        raise PlatformError(f"Parse job id={job_id} not found", status_code=404)
    content = service.get_source_pdf(job)
    encoded_name = quote(job.file_name)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}"},
    )


@router.post("/ppocr/pdf/jobs/{job_id}/pages/{page_no}/retry", response_model=ParsePageItem)
async def retry_ppocr_pdf_page(
    job_id: int,
    page_no: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[PPOcrPdfService, Depends(get_ppocr_pdf_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ParsePageItem:
    try:
        page = service.retry_page(db, job_id, page_no)
        return ParsePageItem(**parse_page_to_dict(page))
    except FileNotFoundError as exc:
        raise PlatformError(str(exc), status_code=404) from exc
