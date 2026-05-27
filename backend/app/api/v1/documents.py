from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.chapter_profile.schemas import (
    ChapterProfileGenerationItemList,
    ChapterProfileGenerationJobList,
    ChapterProfileGenerationJobRead,
    ChapterReviewProfileList,
    CreateChapterProfileGenerationJobResponse,
)
from app.chapter_profile.service import ChapterProfileService, get_chapter_profile_service
from app.db.models import PlanDocument, PlanParseJob, PlanParseResult, PlanSection
from app.db.session import get_db
from app.parsers.factory import ParserConfigError, ParserUnsupportedFileError, get_parser, validate_parser_file
from app.parsers.section_parse_strategies import SECTION_PARSE_MODES, resolve_section_parse_mode
from app.services.document_service import DocumentParseInProgressError, DocumentService, get_document_service
from app.utils.exceptions import PlatformError
from app.utils.jwt import CurrentUser, require_permission

router = APIRouter()

SUPPORTED_PLAN_FILE_EXTENSIONS = (
    ".docx",
    ".xlsx",
    ".csv",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
)
DOCUMENT_TYPES = {"template", "construction_plan"}


class ParseResultItem(BaseModel):
    id: int
    document_id: int
    section_parse_mode: str
    parse_status: str
    parse_progress: int
    section_count: int
    error_message: str | None
    parsed_at: str | None
    created_at: str
    updated_at: str


class DocumentItem(BaseModel):
    id: int
    file_name: str
    file_path: str
    file_size: int
    document_type: str
    section_parse_mode: str
    parse_status: str
    parse_progress: int
    parse_results: list["ParseResultItem"] = Field(default_factory=list)
    created_at: str

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    id: int
    file_name: str
    document_type: str
    section_parse_mode: str
    status: str
    parse_progress: int


class SectionParseModeItem(BaseModel):
    mode: str
    label: str
    description: str


class SectionItem(BaseModel):
    id: int
    document_id: int
    parse_result_id: int
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
    parse_result_id: int | None
    section_parse_mode: str
    parse_status: str
    parse_progress: int
    toc_text: str
    sections: list[SectionItem]


class ParseJobItem(BaseModel):
    id: int
    document_id: int
    file_name: str
    parse_result_id: int | None
    section_parse_mode: str
    job_type: str
    status: str
    progress: int
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class DocumentParseBatchRequest(BaseModel):
    document_ids: list[int] = Field(min_length=1)
    section_parse_modes: list[str] = Field(default_factory=lambda: ["docling_auto"], min_length=1)
    concurrency: int = Field(default=3, ge=1, le=8)


class DocumentParseBatchResponse(BaseModel):
    jobs: list[ParseJobItem]


@router.get("/section-parse-modes", response_model=list[SectionParseModeItem])
async def list_section_parse_modes(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
) -> list[SectionParseModeItem]:
    return [_section_parse_mode_item(mode) for mode in sorted(SECTION_PARSE_MODES)]


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    current_user: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    parser: Annotated[str | None, Form()] = None,
    document_type: Annotated[str, Form()] = "template",
    section_parse_mode: Annotated[str | None, Form()] = None,
) -> DocumentUploadResponse:
    if not (file.filename or "").lower().endswith(SUPPORTED_PLAN_FILE_EXTENSIONS):
        raise PlatformError("Only .docx, .xlsx, .csv, .pdf, and image files are supported.", status_code=400)
    if document_type not in DOCUMENT_TYPES:
        raise PlatformError(f"Invalid document_type: {document_type}", status_code=400)
    _validate_parser(parser, file.filename or "")
    try:
        resolved_section_parse_mode = resolve_section_parse_mode(section_parse_mode)
    except ParserConfigError as exc:
        raise PlatformError(str(exc), status_code=400) from exc
    record = await service.upload(
        db,
        file,
        current_user.username,
        document_type=document_type,
        section_parse_mode=resolved_section_parse_mode,
    )
    background_tasks.add_task(service.parse_in_background, record.id, parser)
    return DocumentUploadResponse(
        id=record.id,
        file_name=record.file_name,
        document_type=record.document_type,
        section_parse_mode=record.section_parse_mode,
        status=record.parse_status,
        parse_progress=record.parse_progress,
    )


@router.get("", response_model=list[DocumentItem])
async def list_documents(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    document_type: Annotated[str | None, Query()] = None,
) -> list[DocumentItem]:
    if document_type and document_type not in DOCUMENT_TYPES:
        raise PlatformError(f"Invalid document_type: {document_type}", status_code=400)
    records = service.list_files(db, document_type=document_type)
    return [
        _to_document_item(r)
        for r in records
    ]


@router.get("/chapter-profile-jobs", response_model=ChapterProfileGenerationJobList)
async def list_chapter_profile_jobs(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    profile_service: Annotated[ChapterProfileService, Depends(get_chapter_profile_service)],
    db: Annotated[Session, Depends(get_db)],
    document_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> ChapterProfileGenerationJobList:
    items, total = profile_service.list_generation_jobs(
        db,
        document_id=document_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ChapterProfileGenerationJobList(items=items, total=total, page=page, page_size=page_size)


@router.get("/chapter-profile-jobs/{job_id}", response_model=ChapterProfileGenerationJobRead)
async def get_chapter_profile_job(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    profile_service: Annotated[ChapterProfileService, Depends(get_chapter_profile_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ChapterProfileGenerationJobRead:
    return profile_service.get_generation_job(db, job_id)


@router.post("/chapter-profile-jobs/{job_id}/restart", response_model=CreateChapterProfileGenerationJobResponse)
async def restart_chapter_profile_job(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    profile_service: Annotated[ChapterProfileService, Depends(get_chapter_profile_service)],
    db: Annotated[Session, Depends(get_db)],
    concurrency: int = Query(3, ge=1, le=8),
) -> CreateChapterProfileGenerationJobResponse:
    job = profile_service.restart_generation_job(db, job_id, concurrency=concurrency)
    return CreateChapterProfileGenerationJobResponse(job=job)


@router.get("/chapter-profile-jobs/{job_id}/items", response_model=ChapterProfileGenerationItemList)
async def list_chapter_profile_job_items(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    profile_service: Annotated[ChapterProfileService, Depends(get_chapter_profile_service)],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> ChapterProfileGenerationItemList:
    items, total = profile_service.list_generation_items(
        db,
        job_id=job_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ChapterProfileGenerationItemList(items=items, total=total, page=page, page_size=page_size)


@router.get("/chapter-profile-jobs/{job_id}/profiles", response_model=ChapterReviewProfileList)
async def list_chapter_profile_job_profiles(
    job_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    profile_service: Annotated[ChapterProfileService, Depends(get_chapter_profile_service)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> ChapterReviewProfileList:
    items, total = profile_service.list_generation_profiles(
        db,
        job_id=job_id,
        page=page,
        page_size=page_size,
    )
    return ChapterReviewProfileList(items=items, total=total, page=page, page_size=page_size)


@router.get("/parse-jobs/list", response_model=list[ParseJobItem])
async def list_parse_jobs(
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    document_type: Annotated[str | None, Query()] = None,
    limit: int = Query(20, ge=1, le=100),
) -> list[ParseJobItem]:
    if document_type and document_type not in DOCUMENT_TYPES:
        raise PlatformError(f"Invalid document_type: {document_type}", status_code=400)
    try:
        return [_to_parse_job_item(job) for job in service.list_recent_parse_jobs(db, document_type=document_type, limit=limit)]
    except SQLAlchemyError as exc:
        raise PlatformError(f"Failed to load parse jobs from database: {exc}", status_code=500) from exc


@router.post("/parse-jobs/batch", response_model=DocumentParseBatchResponse)
async def parse_documents_batch(
    payload: DocumentParseBatchRequest,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> DocumentParseBatchResponse:
    try:
        modes = [resolve_section_parse_mode(mode) for mode in payload.section_parse_modes]
        jobs = service.create_parse_jobs(db, payload.document_ids, modes)
    except DocumentParseInProgressError as exc:
        raise PlatformError(str(exc), status_code=409) from exc
    except (ParserConfigError, ParserUnsupportedFileError) as exc:
        raise PlatformError(str(exc), status_code=400) from exc
    except FileNotFoundError as exc:
        raise PlatformError(str(exc), status_code=404) from exc
    background_tasks.add_task(service.run_parse_jobs_queue, [job.id for job in jobs], payload.concurrency)
    return DocumentParseBatchResponse(jobs=[_to_parse_job_item(job) for job in jobs])


@router.delete("/{record_id}", response_model=DocumentItem)
async def delete_document(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentItem:
    record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
    if not record:
        raise PlatformError(f"Document id={record_id} not found", status_code=404)
    item = _to_document_item(record)
    service.delete_file(db, record_id)
    return item


@router.post("/{record_id}/chapter-profile-jobs", response_model=CreateChapterProfileGenerationJobResponse)
async def create_chapter_profile_job(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    profile_service: Annotated[ChapterProfileService, Depends(get_chapter_profile_service)],
    db: Annotated[Session, Depends(get_db)],
    section_parse_mode: Annotated[str | None, Query()] = None,
    concurrency: int = Query(3, ge=1, le=8),
) -> CreateChapterProfileGenerationJobResponse:
    try:
        job = profile_service.create_generation_job(
            db,
            record_id,
            section_parse_mode=section_parse_mode,
            concurrency=concurrency,
        )
    except ParserConfigError as exc:
        raise PlatformError(str(exc), status_code=400) from exc
    return CreateChapterProfileGenerationJobResponse(job=job)


@router.post("/{record_id}/parse", response_model=DocumentParseResponse)
async def parse_document(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:write"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    parser: Annotated[str | None, Query()] = None,
    section_parse_mode: Annotated[str | None, Query()] = None,
) -> DocumentParseResponse:
    record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
    if not record:
        raise PlatformError(f"Document id={record_id} not found", status_code=404)
    try:
        job = service.create_parse_job(db, record_id, parser, section_parse_mode)
    except DocumentParseInProgressError as exc:
        raise PlatformError(str(exc), status_code=409) from exc
    except (ParserConfigError, ParserUnsupportedFileError) as exc:
        raise PlatformError(str(exc), status_code=400) from exc
    except FileNotFoundError as exc:
        raise PlatformError(str(exc), status_code=404) from exc
    except Exception as exc:
        raise PlatformError(f"Document parse enqueue failed: {exc}", status_code=500) from exc
    background_tasks.add_task(service.run_parse_job, job.id)
    result, sections = service.get_sections(db, record_id, job.section_parse_mode)
    return _to_document_parse_response(record, result, sections, job.section_parse_mode)


@router.get("/{record_id}/sections", response_model=DocumentParseResponse)
async def get_document_sections(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    section_parse_mode: Annotated[str | None, Query()] = None,
) -> DocumentParseResponse:
    record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
    if not record:
        raise PlatformError(f"Document id={record_id} not found", status_code=404)
    try:
        result, sections = service.get_sections(db, record_id, section_parse_mode or record.section_parse_mode)
    except ParserConfigError as exc:
        raise PlatformError(str(exc), status_code=400) from exc
    return _to_document_parse_response(record, result, sections, section_parse_mode or record.section_parse_mode)


@router.get("/{record_id}/preview")
async def preview_document_pdf(
    record_id: int,
    _: Annotated[CurrentUser, Depends(require_permission("knowledge:read"))],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
    if not record:
        raise PlatformError(f"Document id={record_id} not found", status_code=404)
    if not record.file_name.lower().endswith(".pdf"):
        raise PlatformError("Only PDF preview is supported.", status_code=400)
    content = service.get_file_bytes(record)
    encoded_name = quote(record.file_name)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}"},
    )


def _build_section_tree(sections: list[PlanSection]) -> list[SectionItem]:
    items = {
        section.id: SectionItem(
            id=section.id,
            document_id=section.document_id,
            parse_result_id=section.parse_result_id,
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


def _to_document_item(record: PlanDocument) -> DocumentItem:
    return DocumentItem(
        id=record.id,
        file_name=record.file_name,
        file_path=record.file_path,
        file_size=record.file_size,
        document_type=record.document_type,
        section_parse_mode=getattr(record, "section_parse_mode", None) or "docling_auto",
        parse_status=record.parse_status,
        parse_progress=getattr(record, "parse_progress", 0) or 0,
        parse_results=[_to_parse_result_item(result) for result in getattr(record, "parse_results", [])],
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


def _to_document_parse_response(
    record: PlanDocument,
    result: PlanParseResult | None,
    sections: list[PlanSection],
    fallback_mode: str,
) -> DocumentParseResponse:
    return DocumentParseResponse(
        id=record.id,
        file_name=record.file_name,
        parse_result_id=result.id if result else None,
        section_parse_mode=result.section_parse_mode if result else resolve_section_parse_mode(fallback_mode),
        parse_status=result.parse_status if result else "uploaded",
        parse_progress=result.parse_progress if result else 0,
        toc_text=result.toc_text if result else _sections_to_toc_text(sections),
        sections=_build_section_tree(sections),
    )


def _to_parse_result_item(result: PlanParseResult) -> ParseResultItem:
    return ParseResultItem(
        id=result.id,
        document_id=result.document_id,
        section_parse_mode=result.section_parse_mode,
        parse_status=result.parse_status,
        parse_progress=result.parse_progress,
        section_count=result.section_count,
        error_message=result.error_message,
        parsed_at=result.parsed_at.isoformat() if result.parsed_at else None,
        created_at=result.created_at.isoformat() if result.created_at else "",
        updated_at=result.updated_at.isoformat() if result.updated_at else "",
    )


def _to_parse_job_item(job: PlanParseJob) -> ParseJobItem:
    return ParseJobItem(
        id=job.id,
        document_id=job.document_id,
        file_name=job.document.file_name if job.document else "",
        parse_result_id=job.parse_result_id,
        section_parse_mode=job.section_parse_mode,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


def _section_parse_mode_item(mode: str) -> SectionParseModeItem:
    labels = {
        "docling_auto": (
            "Docling 线性分章（原方案）",
            "Docling 转 Markdown，auto 策略线性扫描，不启用目录大纲。",
        ),
        "docling_toc_outline": (
            "Docling 目录大纲分章",
            "Docling 转 Markdown，识别目录/目次并与正文标题匹配后填充章节内容。",
        ),
        "python_docx": (
            "python-docx 分章",
            "使用 python-docx 读取 Word 段落和标题样式，跳过目录段落和目录区域。",
        ),
        "word_native": (
            "Word 原生分章",
            "直接解析 OOXML：Heading 样式与编号标题，跳过 TOC 样式段落。",
        ),
    }
    label, description = labels.get(mode, (mode, ""))
    return SectionParseModeItem(mode=mode, label=label, description=description)


def _sections_to_toc_text(sections: list[PlanSection]) -> str:
    return "\n".join(f"{'  ' * max(section.level - 1, 0)}{section.title}" for section in sections)


def _validate_parser(parser: str | None, file_name: str | None = None) -> None:
    try:
        get_parser(parser, file_name)
        if file_name:
            validate_parser_file(parser, file_name)
    except (ParserConfigError, ParserUnsupportedFileError) as exc:
        raise PlatformError(str(exc), status_code=400) from exc
