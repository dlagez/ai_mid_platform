from __future__ import annotations

import hashlib
import io
import os
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

import fitz
from fastapi import UploadFile
from minio import Minio
from sqlalchemy.orm import Session, selectinload

from app.db.models import DocumentMarkdownMap, ParseJob, ParsePageResult, ParseResult
from configs.settings import settings


class PPOcrPdfService:
    def __init__(self) -> None:
        self._minio = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        self._bucket = settings.minio_bucket_documents

    def _ensure_bucket(self) -> None:
        if not self._minio.bucket_exists(self._bucket):
            self._minio.make_bucket(self._bucket)

    async def create_pdf_job(
        self,
        db: Session,
        file: UploadFile,
        created_by: str,
        *,
        dpi: int | None = None,
        batch_size: int | None = None,
        page_timeout_seconds: int | None = None,
        min_confidence: float | None = None,
    ) -> ParseJob:
        file_name = os.path.basename(file.filename or "original.pdf")
        if not file_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files can use the page-level PPOCR pipeline.")

        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        page_count = _get_pdf_page_count(content)
        if page_count < 1:
            raise ValueError("PDF has no pages.")

        self._ensure_bucket()
        file_id = uuid.uuid4().hex
        parse_metadata = {
            "dpi": dpi or settings.ppocr_pdf_dpi,
            "ocr_mode": "ppocr_page_ocr",
            "parse_mode": "pdf_page_render",
            "fileType": 1,
            "batch_size": batch_size or settings.ppocr_pdf_batch_size,
            "page_timeout_seconds": page_timeout_seconds or settings.ppocr_page_timeout_seconds,
            "min_confidence": min_confidence if min_confidence is not None else settings.ppocr_pdf_min_confidence,
            "source_content_type": file.content_type,
        }

        job = ParseJob(
            file_id=file_id,
            file_name=file_name,
            file_size=len(content),
            file_hash=file_hash,
            page_count=page_count,
            source_file_path="pending",
            parser_provider="ppocr",
            parse_mode="page_ocr",
            ocr_endpoint=settings.ppocr_ocr_endpoint,
            status="queued",
            dpi=parse_metadata["dpi"],
            batch_size=parse_metadata["batch_size"],
            page_timeout_seconds=parse_metadata["page_timeout_seconds"],
            min_confidence=parse_metadata["min_confidence"],
            total_pages=page_count,
            parse_metadata=parse_metadata,
            created_by=created_by,
        )
        db.add(job)
        db.flush()

        source_object_name = f"parse-results/{file_id}/{job.id}/source/original.pdf"
        self._minio.put_object(
            bucket_name=self._bucket,
            object_name=source_object_name,
            data=io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/pdf",
        )
        job.source_file_path = f"{self._bucket}/{source_object_name}"

        for page_no in range(1, page_count + 1):
            db.add(ParsePageResult(job_id=job.id, page_no=page_no, status="queued"))

        db.commit()
        db.refresh(job)

        from app.workers.ppocr_pdf_tasks import submit_parse_job_batches

        submit_parse_job_batches.delay(job.id)
        return job

    def list_jobs(self, db: Session) -> list[ParseJob]:
        return db.query(ParseJob).order_by(ParseJob.created_at.desc()).all()

    def get_job(self, db: Session, job_id: int) -> ParseJob | None:
        return (
            db.query(ParseJob)
            .options(selectinload(ParseJob.pages), selectinload(ParseJob.result))
            .filter(ParseJob.id == job_id)
            .first()
        )

    def get_markdown(self, job: ParseJob) -> str:
        path = job.result_markdown_path or (job.result.markdown_file_path if job.result else None)
        if not path:
            return ""
        response = self._minio.get_object(self._bucket, _object_name(path))
        try:
            return response.read().decode("utf-8", errors="replace")
        finally:
            response.close()
            response.release_conn()

    def get_markdown_maps(self, db: Session, job_id: int) -> list[DocumentMarkdownMap]:
        return (
            db.query(DocumentMarkdownMap)
            .filter(DocumentMarkdownMap.job_id == job_id)
            .order_by(DocumentMarkdownMap.page_no.asc())
            .all()
        )

    def retry_page(self, db: Session, job_id: int, page_no: int) -> ParsePageResult:
        page = (
            db.query(ParsePageResult)
            .filter(ParsePageResult.job_id == job_id, ParsePageResult.page_no == page_no)
            .first()
        )
        if not page:
            raise FileNotFoundError(f"Page job not found: job_id={job_id}, page_no={page_no}")
        job = db.query(ParseJob).filter(ParseJob.id == job_id).first()
        if not job:
            raise FileNotFoundError(f"Parse job not found: {job_id}")

        page.status = "queued"
        page.error_message = None
        page.started_at = None
        page.completed_at = None
        job.status = "running"
        job.completed_at = None
        db.query(DocumentMarkdownMap).filter(DocumentMarkdownMap.job_id == job_id).delete()
        db.query(ParseResult).filter(ParseResult.job_id == job_id).delete()
        db.commit()
        db.refresh(page)

        from app.workers.ppocr_pdf_tasks import parse_pdf_page

        parse_pdf_page.delay(page.id)
        return page


def _get_pdf_page_count(content: bytes) -> int:
    with fitz.open(stream=content, filetype="pdf") as doc:
        return doc.page_count


def _object_name(path: str) -> str:
    return path.split("/", 1)[1]


def parse_job_to_dict(job: ParseJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "file_id": job.file_id,
        "file_name": job.file_name,
        "file_size": job.file_size,
        "file_hash": job.file_hash,
        "page_count": job.page_count,
        "source_file_path": job.source_file_path,
        "parser_provider": job.parser_provider,
        "parse_mode": job.parse_mode,
        "ocr_endpoint": job.ocr_endpoint,
        "status": job.status,
        "dpi": job.dpi,
        "batch_size": job.batch_size,
        "page_timeout_seconds": job.page_timeout_seconds,
        "min_confidence": job.min_confidence,
        "low_confidence_flag": job.low_confidence_flag,
        "total_pages": job.total_pages,
        "succeeded_pages": job.succeeded_pages,
        "failed_pages": job.failed_pages,
        "low_confidence_pages": job.low_confidence_pages,
        "avg_confidence": job.avg_confidence,
        "block_count": job.block_count,
        "metadata": job.parse_metadata or {},
        "error_message": job.error_message,
        "result_markdown_path": job.result_markdown_path,
        "result_json_path": job.result_json_path,
        "raw_result_path": job.raw_result_path,
        "created_by": job.created_by,
        "created_at": _dt(job.created_at),
        "started_at": _dt(job.started_at),
        "completed_at": _dt(job.completed_at),
    }


def parse_page_to_dict(page: ParsePageResult) -> dict[str, Any]:
    return {
        "id": page.id,
        "job_id": page.job_id,
        "page_no": page.page_no,
        "status": page.status,
        "image_path": page.image_path,
        "raw_json_path": page.raw_json_path,
        "text": page.text,
        "markdown_content": page.markdown_content,
        "rec_texts": page.rec_texts or [],
        "rec_scores": page.rec_scores or [],
        "rec_polys": page.rec_polys or [],
        "average_confidence": page.average_confidence,
        "min_confidence": page.min_confidence,
        "block_count": page.block_count,
        "low_confidence_flag": page.low_confidence_flag,
        "retry_count": page.retry_count,
        "error_message": page.error_message,
        "started_at": _dt(page.started_at),
        "completed_at": _dt(page.completed_at),
    }


def markdown_map_to_dict(item: DocumentMarkdownMap) -> dict[str, Any]:
    return {
        "id": item.id,
        "job_id": item.job_id,
        "page_result_id": item.page_result_id,
        "page_no": item.page_no,
        "markdown_start": item.markdown_start,
        "markdown_end": item.markdown_end,
        "anchor": item.anchor,
        "block_count": item.block_count,
        "created_at": _dt(item.created_at),
    }


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


_ppocr_pdf_service: PPOcrPdfService | None = None


def get_ppocr_pdf_service() -> Generator[PPOcrPdfService, None, None]:
    global _ppocr_pdf_service
    if _ppocr_pdf_service is None:
        _ppocr_pdf_service = PPOcrPdfService()
    yield _ppocr_pdf_service
