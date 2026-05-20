from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any

import fitz
from celery.exceptions import SoftTimeLimitExceeded
from minio import Minio

from app.db.models import DocumentMarkdownMap, ParseJob, ParsePageResult, ParseResult
from app.db.session import SessionLocal
from app.parsers.ppocr_page import PPOcrPageClient
from app.workers.celery_worker import celery_app
from configs.settings import settings


TERMINAL_PAGE_STATUSES = {"success", "failed"}


@celery_app.task(name="ppocr.submit_parse_job_batches")
def submit_parse_job_batches(job_id: int) -> None:
    """Submit page OCR tasks in configurable batches.

    The page rows already exist in parse_page_result. This task only fans them
    out, which keeps the upload API fast and makes large PDFs manageable.
    """

    db = SessionLocal()
    try:
        job = db.query(ParseJob).filter(ParseJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        job.started_at = job.started_at or datetime.utcnow()
        db.commit()

        pages = (
            db.query(ParsePageResult)
            .filter(ParsePageResult.job_id == job_id)
            .order_by(ParsePageResult.page_no.asc())
            .all()
        )
        batch_size = max(job.batch_size or settings.ppocr_pdf_batch_size, 1)
        for batch_index, start in enumerate(range(0, len(pages), batch_size)):
            batch = pages[start : start + batch_size]
            # Small countdown spaces out huge PDFs without changing worker concurrency.
            countdown = batch_index * 2
            for page in batch:
                parse_pdf_page.apply_async(
                    args=[page.id],
                    countdown=countdown,
                    soft_time_limit=job.page_timeout_seconds + 10,
                    time_limit=job.page_timeout_seconds + 30,
                )
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="ppocr.parse_pdf_page",
    max_retries=settings.ppocr_pdf_max_retries,
    default_retry_delay=5,
)
def parse_pdf_page(self, page_result_id: int) -> None:
    """Render one PDF page, call PP-OCR, and persist page-level quality data."""

    db = SessionLocal()
    page: ParsePageResult | None = None
    job_id: int | None = None
    try:
        page = db.query(ParsePageResult).filter(ParsePageResult.id == page_result_id).first()
        if not page:
            return
        job = db.query(ParseJob).filter(ParseJob.id == page.job_id).first()
        if not job:
            return
        job_id = job.id
        # retry_count is cumulative across automatic and manual retries.
        page.retry_count = (page.retry_count or 0) + 1
        page.status = "running"
        page.started_at = datetime.utcnow()
        page.error_message = None
        job.status = "running"
        db.commit()

        minio = _minio_client()
        pdf_bytes = _read_minio_bytes(minio, job.source_file_path)
        png_bytes = _render_pdf_page(pdf_bytes, page.page_no, job.dpi)
        image_object_name = f"parse-results/{job.file_id}/{job.id}/pages/page_{page.page_no:03d}.png"
        _put_bytes(minio, image_object_name, png_bytes, "image/png")

        client = PPOcrPageClient(timeout_seconds=job.page_timeout_seconds, ocr_endpoint=job.ocr_endpoint)
        output = client.ocr_png(png_bytes)

        raw_json_bytes = json.dumps(output.raw_json, ensure_ascii=False).encode("utf-8")
        raw_json_object_name = f"parse-results/{job.file_id}/{job.id}/json/pages/page_{page.page_no:03d}.json"
        _put_bytes(minio, raw_json_object_name, raw_json_bytes, "application/json; charset=utf-8")

        page.image_path = f"{settings.minio_bucket_documents}/{image_object_name}"
        page.raw_json_path = f"{settings.minio_bucket_documents}/{raw_json_object_name}"
        page.text = output.text
        page.markdown_content = output.markdown_content
        page.rec_texts = output.rec_texts
        page.rec_scores = output.rec_scores
        page.rec_polys = output.rec_polys
        page.average_confidence = output.average_confidence
        page.min_confidence = output.min_confidence
        page.block_count = output.block_count
        page.low_confidence_flag = _is_low_confidence(output.average_confidence, job.min_confidence)
        page.status = "success"
        page.completed_at = datetime.utcnow()
        db.commit()
        finalize_parse_job.delay(job.id)
    except SoftTimeLimitExceeded as exc:
        _handle_page_failure(db, page, job_id, self, exc)
    except Exception as exc:
        _handle_page_failure(db, page, job_id, self, exc)
    finally:
        db.close()


@celery_app.task(name="ppocr.finalize_parse_job")
def finalize_parse_job(job_id: int) -> None:
    """Merge page Markdown, write final artifacts, and compute job status.

    This task is idempotent. Each page task invokes it when it reaches a
    terminal state; if any page is still queued/running, finalization exits.
    """

    db = SessionLocal()
    try:
        job = db.query(ParseJob).filter(ParseJob.id == job_id).first()
        if not job:
            return
        pages = (
            db.query(ParsePageResult)
            .filter(ParsePageResult.job_id == job_id)
            .order_by(ParsePageResult.page_no.asc())
            .all()
        )
        if not pages:
            return

        _refresh_job_metrics(job, pages)
        if any(page.status not in TERMINAL_PAGE_STATUSES for page in pages):
            db.commit()
            return

        succeeded = [page for page in pages if page.status == "success"]
        failed = [page for page in pages if page.status == "failed"]
        if len(succeeded) == len(pages):
            final_status = "success"
        elif succeeded:
            final_status = "partial_success"
        else:
            final_status = "failed"

        minio = _minio_client()
        db.query(DocumentMarkdownMap).filter(DocumentMarkdownMap.job_id == job_id).delete()
        db.query(ParseResult).filter(ParseResult.job_id == job_id).delete()
        db.flush()

        document_markdown = ""
        for page in pages:
            page_markdown = _page_markdown(page)
            start = len(document_markdown)
            document_markdown += page_markdown
            end = len(document_markdown)
            db.add(
                DocumentMarkdownMap(
                    job_id=job.id,
                    page_result_id=page.id,
                    page_no=page.page_no,
                    markdown_start=start,
                    markdown_end=end,
                    anchor=f"page-{page.page_no}",
                    block_count=page.block_count,
                )
            )

        result_payload = _document_result_payload(job, pages, final_status)
        raw_payload = {
            "job_id": job.id,
            "file_id": job.file_id,
            "raw_pages": [
                {
                    "page_no": page.page_no,
                    "status": page.status,
                    "raw_json_path": page.raw_json_path,
                    "image_path": page.image_path,
                    "retry_count": page.retry_count,
                    "error_message": page.error_message,
                }
                for page in pages
            ],
        }

        markdown_bytes = document_markdown.encode("utf-8")
        document_json_bytes = json.dumps(result_payload, ensure_ascii=False).encode("utf-8")
        raw_json_bytes = json.dumps(raw_payload, ensure_ascii=False).encode("utf-8")
        markdown_object_name = f"parse-results/{job.file_id}/{job.id}/markdown/document.md"
        document_json_object_name = f"parse-results/{job.file_id}/{job.id}/json/document.json"
        raw_result_object_name = f"parse-results/{job.file_id}/{job.id}/json/raw_result.json"
        _put_bytes(minio, markdown_object_name, markdown_bytes, "text/markdown; charset=utf-8")
        _put_bytes(minio, document_json_object_name, document_json_bytes, "application/json; charset=utf-8")
        _put_bytes(minio, raw_result_object_name, raw_json_bytes, "application/json; charset=utf-8")

        job.status = final_status
        job.result_markdown_path = f"{settings.minio_bucket_documents}/{markdown_object_name}"
        job.result_json_path = f"{settings.minio_bucket_documents}/{document_json_object_name}"
        job.raw_result_path = f"{settings.minio_bucket_documents}/{raw_result_object_name}"
        job.completed_at = datetime.utcnow()
        job.error_message = _final_error_message(failed)
        db.add(
            ParseResult(
                job_id=job.id,
                status=final_status,
                markdown_file_path=job.result_markdown_path,
                json_file_path=job.result_json_path,
                raw_result_file_path=job.raw_result_path,
                markdown_file_size=len(markdown_bytes),
                json_file_size=len(document_json_bytes),
                page_count=job.page_count,
                succeeded_pages=job.succeeded_pages,
                failed_pages=job.failed_pages,
                low_confidence_pages=job.low_confidence_pages,
                avg_confidence=job.avg_confidence,
                block_count=job.block_count,
                parse_metadata=job.parse_metadata,
            )
        )
        db.commit()
    finally:
        db.close()


def _handle_page_failure(db, page: ParsePageResult | None, job_id: int | None, task, exc: Exception) -> None:
    if page is None:
        raise exc
    if task.request.retries < task.max_retries:
        page.status = "queued"
        page.error_message = str(exc)[:4000]
        page.completed_at = datetime.utcnow()
        db.commit()
        raise task.retry(exc=exc, countdown=min(60, 5 * (task.request.retries + 1)))

    page.status = "failed"
    page.error_message = str(exc)[:4000]
    page.completed_at = datetime.utcnow()
    db.commit()
    if job_id is not None:
        finalize_parse_job.delay(job_id)


def _render_pdf_page(pdf_bytes: bytes, page_no: int, dpi: int) -> bytes:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc.load_page(page_no - 1)
        zoom = dpi / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")


def _minio_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )


def _read_minio_bytes(minio: Minio, path: str) -> bytes:
    response = minio.get_object(settings.minio_bucket_documents, _object_name(path))
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def _put_bytes(minio: Minio, object_name: str, content: bytes, content_type: str) -> None:
    minio.put_object(
        bucket_name=settings.minio_bucket_documents,
        object_name=object_name,
        data=io.BytesIO(content),
        length=len(content),
        content_type=content_type,
    )


def _object_name(path: str) -> str:
    return path.split("/", 1)[1]


def _is_low_confidence(avg_confidence: float | None, threshold: float) -> bool:
    return avg_confidence is None or avg_confidence < threshold


def _refresh_job_metrics(job: ParseJob, pages: list[ParsePageResult]) -> None:
    succeeded = [page for page in pages if page.status == "success"]
    failed = [page for page in pages if page.status == "failed"]
    confidence_values = [
        page.average_confidence for page in succeeded if page.average_confidence is not None
    ]
    job.total_pages = len(pages)
    job.succeeded_pages = len(succeeded)
    job.failed_pages = len(failed)
    job.low_confidence_pages = sum(1 for page in succeeded if page.low_confidence_flag)
    job.low_confidence_flag = job.low_confidence_pages > 0
    job.block_count = sum(page.block_count for page in succeeded)
    job.avg_confidence = (
        sum(confidence_values) / len(confidence_values)
        if confidence_values
        else None
    )


def _page_markdown(page: ParsePageResult) -> str:
    anchor = f'<a id="page-{page.page_no}"></a>'
    if page.status == "success":
        body = page.markdown_content.strip() or page.text.strip()
    else:
        body = f"> OCR failed for page {page.page_no}: {page.error_message or 'unknown error'}"
    return f"{anchor}\n\n<!-- page:{page.page_no} status:{page.status} -->\n\n{body}\n\n"


def _document_result_payload(job: ParseJob, pages: list[ParsePageResult], status: str) -> dict[str, Any]:
    return {
        "job": {
            "id": job.id,
            "file_id": job.file_id,
            "file_name": job.file_name,
            "file_size": job.file_size,
            "file_hash": job.file_hash,
            "page_count": job.page_count,
            "status": status,
            "parser_provider": job.parser_provider,
            "parse_mode": job.parse_mode,
            "metadata": job.parse_metadata,
            "avg_confidence": job.avg_confidence,
            "block_count": job.block_count,
            "low_confidence_flag": job.low_confidence_flag,
        },
        "pages": [
            {
                "page_no": page.page_no,
                "status": page.status,
                "image_path": page.image_path,
                "raw_json_path": page.raw_json_path,
                "average_confidence": page.average_confidence,
                "min_confidence": page.min_confidence,
                "low_confidence_flag": page.low_confidence_flag,
                "block_count": page.block_count,
                "retry_count": page.retry_count,
                "rec_texts": page.rec_texts,
                "rec_scores": page.rec_scores,
                "rec_polys": page.rec_polys,
            }
            for page in pages
        ],
    }


def _final_error_message(failed_pages: list[ParsePageResult]) -> str | None:
    if not failed_pages:
        return None
    page_numbers = ", ".join(str(page.page_no) for page in failed_pages[:20])
    suffix = "..." if len(failed_pages) > 20 else ""
    return f"Failed pages: {page_numbers}{suffix}"
