import io
import os
import tempfile
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from fastapi import UploadFile
from minio import Minio
from sqlalchemy.orm import Session

from app.db.models import PlanDocument, PlanParseJob, PlanParseResult, PlanSection
from app.db.session import SessionLocal
from app.parsers.base import ParsedSection
from app.parsers.factory import get_parser, validate_parser_file
from app.parsers.section_parse_strategies import (
    DEFAULT_SECTION_PARSE_MODE,
    parse_construction_plan_sections,
    resolve_section_parse_mode,
)
from configs.settings import settings


RUNNING_PARSE_STATUSES = {"queued", "running"}


class DocumentParseInProgressError(RuntimeError):
    """Raised when a document and parse method already have a queued/running job."""


class DocumentService:
    _parse_locks: dict[tuple[int, str], threading.Lock] = {}
    _parse_locks_guard = threading.Lock()

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

    async def upload(
        self,
        db: Session,
        file: UploadFile,
        uploaded_by: str,
        document_type: str = "template",
        section_parse_mode: str | None = None,
    ) -> PlanDocument:
        del uploaded_by
        self._ensure_bucket()
        content = await file.read()
        file_name = file.filename or "unnamed.docx"
        object_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{file_name}"
        resolved_section_parse_mode = resolve_section_parse_mode(section_parse_mode)

        self._minio.put_object(
            bucket_name=self._bucket,
            object_name=object_name,
            data=io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/octet-stream",
        )

        record = PlanDocument(
            file_name=file_name,
            file_path=f"{self._bucket}/{object_name}",
            file_size=len(content),
            document_type=document_type,
            section_parse_mode=resolved_section_parse_mode,
            parse_status="uploaded",
            parse_progress=0,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_files(self, db: Session, document_type: str | None = None) -> list[PlanDocument]:
        query = db.query(PlanDocument)
        if document_type:
            query = query.filter(PlanDocument.document_type == document_type)
        return query.order_by(PlanDocument.created_at.desc()).all()

    def delete_file(self, db: Session, record_id: int) -> PlanDocument:
        record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
        if not record:
            raise FileNotFoundError(f"PlanDocument id={record_id} not found")

        try:
            object_name = record.file_path.split("/", 1)[1]
            self._minio.remove_object(self._bucket, object_name)
        except Exception:
            pass

        db.delete(record)
        db.commit()
        return record

    def create_parse_job(
        self,
        db: Session,
        record_id: int,
        parser_provider: str | None = None,
        section_parse_mode: str | None = None,
    ) -> PlanParseJob:
        record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
        if not record:
            raise FileNotFoundError(f"PlanDocument id={record_id} not found")
        validate_parser_file(parser_provider, record.file_name)

        mode = resolve_section_parse_mode(section_parse_mode or record.section_parse_mode or DEFAULT_SECTION_PARSE_MODE)
        running = (
            db.query(PlanParseJob)
            .filter(
                PlanParseJob.document_id == record.id,
                PlanParseJob.section_parse_mode == mode,
                PlanParseJob.status.in_(RUNNING_PARSE_STATUSES),
            )
            .first()
        )
        if running:
            raise DocumentParseInProgressError(f"PlanDocument id={record_id}, mode={mode} is already queued/running")

        result = self.get_or_create_parse_result(db, record.id, mode)
        job = PlanParseJob(
            document_id=record.id,
            parse_result_id=result.id,
            parser_provider=parser_provider,
            section_parse_mode=mode,
            job_type="reparse" if result.parse_status == "parsed" else "parse",
            status="queued",
            progress=0,
        )
        result.parse_status = "queued"
        result.parse_progress = 0
        result.error_message = None
        record.section_parse_mode = mode
        record.parse_status = "queued"
        record.parse_progress = 0
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def create_parse_jobs(
        self,
        db: Session,
        record_ids: list[int],
        section_parse_modes: list[str],
        parser_provider: str | None = None,
    ) -> list[PlanParseJob]:
        jobs: list[PlanParseJob] = []
        for record_id in record_ids:
            for mode in section_parse_modes:
                jobs.append(self.create_parse_job(db, record_id, parser_provider, mode))
        return jobs

    def run_parse_jobs_queue(self, job_ids: list[int], concurrency: int = 3) -> None:
        max_workers = max(1, min(concurrency, 8))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.run_parse_job, job_id) for job_id in job_ids]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    # Individual jobs persist their own failed status; keep the queue draining.
                    pass

    def parse_in_background(self, record_id: int, parser_provider: str | None = None) -> None:
        db = SessionLocal()
        try:
            job = self.create_parse_job(db, record_id, parser_provider, None)
        finally:
            db.close()
        self.run_parse_job(job.id)

    def run_parse_job(self, job_id: int) -> PlanParseResult:
        db = SessionLocal()
        try:
            job = db.query(PlanParseJob).filter(PlanParseJob.id == job_id).first()
            if not job:
                raise FileNotFoundError(f"PlanParseJob id={job_id} not found")
            return self._run_parse_job(db, job)
        finally:
            db.close()

    def _run_parse_job(self, db: Session, job: PlanParseJob) -> PlanParseResult:
        lock = self._record_parse_lock(job.document_id, job.section_parse_mode)
        if not lock.acquire(blocking=False):
            job.status = "queued"
            db.commit()
            raise DocumentParseInProgressError(
                f"PlanDocument id={job.document_id}, mode={job.section_parse_mode} is already parsing"
            )
        tmp_path: str | None = None
        try:
            record = db.query(PlanDocument).filter(PlanDocument.id == job.document_id).first()
            if not record:
                raise FileNotFoundError(f"PlanDocument id={job.document_id} not found")
            result = self.get_or_create_parse_result(db, record.id, job.section_parse_mode)
            job.parse_result_id = result.id
            self._update_job_progress(db, job, result, record, "running", 5)

            validate_parser_file(job.parser_provider, record.file_name)
            tmp_path = self._download_to_temp(record)
            self._update_job_progress(db, job, result, record, "running", 25)
            sections = self._parse_document_sections(record, tmp_path, job.parser_provider, job.section_parse_mode)
            self._update_job_progress(db, job, result, record, "running", 65)

            db.query(PlanSection).filter(PlanSection.parse_result_id == result.id).delete(
                synchronize_session=False
            )
            db.flush()
            self._set_job_progress(job, result, record, "running", 75)
            sort_counter = 1
            for section in sections:
                sort_counter = self._insert_section_tree(db, record.id, result.id, None, section, sort_counter)

            result.section_count = sort_counter - 1
            result.toc_text = "\n".join(_sections_to_toc_lines(sections))
            result.error_message = None
            result.parsed_at = datetime.utcnow()
            self._update_job_progress(db, job, result, record, "running", 90)
            self._update_job_progress(db, job, result, record, "parsed", 100)
            job.status = "success"
            job.progress = 100
            job.finished_at = datetime.utcnow()
            db.commit()
            db.refresh(result)
            return result
        except Exception as exc:
            db.rollback()
            failed_job = db.query(PlanParseJob).filter(PlanParseJob.id == job.id).first()
            if failed_job:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)
                failed_job.finished_at = datetime.utcnow()
                failed_result = self.get_or_create_parse_result(db, failed_job.document_id, failed_job.section_parse_mode)
                failed_result.parse_status = "failed"
                failed_result.error_message = str(exc)
                failed_result.parse_progress = failed_result.parse_progress or failed_job.progress or 0
                document = db.query(PlanDocument).filter(PlanDocument.id == failed_job.document_id).first()
                if document:
                    document.parse_status = "failed"
                    document.parse_progress = failed_result.parse_progress
                db.commit()
            raise
        finally:
            lock.release()
            if tmp_path:
                os.unlink(tmp_path)

    @classmethod
    def _record_parse_lock(cls, record_id: int, section_parse_mode: str) -> threading.Lock:
        key = (record_id, section_parse_mode)
        with cls._parse_locks_guard:
            lock = cls._parse_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._parse_locks[key] = lock
            return lock

    def get_or_create_parse_result(self, db: Session, record_id: int, section_parse_mode: str) -> PlanParseResult:
        mode = resolve_section_parse_mode(section_parse_mode)
        result = (
            db.query(PlanParseResult)
            .filter(PlanParseResult.document_id == record_id, PlanParseResult.section_parse_mode == mode)
            .first()
        )
        if result:
            return result
        result = PlanParseResult(
            document_id=record_id,
            section_parse_mode=mode,
            parse_status="uploaded",
            parse_progress=0,
        )
        db.add(result)
        db.flush()
        return result

    def get_parse_result(self, db: Session, record_id: int, section_parse_mode: str | None = None) -> PlanParseResult | None:
        mode = resolve_section_parse_mode(section_parse_mode or DEFAULT_SECTION_PARSE_MODE)
        return (
            db.query(PlanParseResult)
            .filter(PlanParseResult.document_id == record_id, PlanParseResult.section_parse_mode == mode)
            .first()
        )

    def get_latest_parsed_result(self, db: Session, record_id: int) -> PlanParseResult | None:
        return (
            db.query(PlanParseResult)
            .filter(PlanParseResult.document_id == record_id, PlanParseResult.parse_status == "parsed")
            .order_by(PlanParseResult.parsed_at.desc().nullslast(), PlanParseResult.id.desc())
            .first()
        )

    def list_recent_parse_jobs(
        self,
        db: Session,
        document_type: str | None = None,
        limit: int = 20,
    ) -> list[PlanParseJob]:
        query = db.query(PlanParseJob).join(PlanDocument, PlanDocument.id == PlanParseJob.document_id)
        if document_type:
            query = query.filter(PlanDocument.document_type == document_type)
        return query.order_by(PlanParseJob.created_at.desc()).limit(limit).all()

    def get_sections(
        self,
        db: Session,
        record_id: int,
        section_parse_mode: str | None = None,
    ) -> tuple[PlanParseResult | None, list[PlanSection]]:
        result = self.get_parse_result(db, record_id, section_parse_mode)
        if not result:
            return None, []
        sections = (
            db.query(PlanSection)
            .filter(PlanSection.parse_result_id == result.id)
            .order_by(PlanSection.sort_no.asc())
            .all()
        )
        return result, sections

    def get_file_bytes(self, record: PlanDocument) -> bytes:
        object_name = record.file_path.split("/", 1)[1]
        response = self._minio.get_object(self._bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def get_toc_text(self, db: Session, record_id: int, parser_provider: str | None = None) -> str:
        record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
        if not record:
            raise FileNotFoundError(f"PlanDocument id={record_id} not found")
        validate_parser_file(parser_provider, record.file_name)
        tmp_path = self._download_to_temp(record)
        try:
            sections = self._parse_document_sections(
                record,
                tmp_path,
                parser_provider,
                record.section_parse_mode or DEFAULT_SECTION_PARSE_MODE,
            )
            return "\n".join(_sections_to_toc_lines(sections))
        finally:
            os.unlink(tmp_path)

    def _parse_document_sections(
        self,
        record: PlanDocument,
        file_path: str,
        parser_provider: str | None,
        section_parse_mode: str | None,
    ) -> list[ParsedSection]:
        suffix = os.path.splitext(record.file_name)[1].lower()
        mode = resolve_section_parse_mode(section_parse_mode)
        if suffix == ".docx" or mode == "ppocr_toc_outline":
            return parse_construction_plan_sections(
                file_path,
                record.file_name,
                section_parse_mode=mode,
                document_type=record.document_type,
            )
        parser = get_parser(parser_provider, record.file_name)
        return parser.parse_sections(file_path, record.file_name)

    def _download_to_temp(self, record: PlanDocument) -> str:
        object_name = record.file_path.split("/", 1)[1]
        response = self._minio.get_object(self._bucket, object_name)
        suffix = os.path.splitext(record.file_name)[1] or ".docx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            try:
                tmp.write(response.read())
            finally:
                response.close()
                response.release_conn()
            return tmp.name

    def _insert_section_tree(
        self,
        db: Session,
        document_id: int,
        parse_result_id: int,
        parent_id: int | None,
        parsed: ParsedSection,
        sort_no: int,
    ) -> int:
        section = PlanSection(
            document_id=document_id,
            parse_result_id=parse_result_id,
            parent_id=parent_id,
            level=parsed.level,
            title=parsed.title,
            section_no=parsed.section_no,
            content=parsed.content,
            sort_no=sort_no,
        )
        db.add(section)
        db.flush()
        next_sort_no = sort_no + 1
        for child in parsed.children:
            next_sort_no = self._insert_section_tree(
                db,
                document_id,
                parse_result_id,
                section.id,
                child,
                next_sort_no,
            )
        return next_sort_no

    def _update_job_progress(
        self,
        db: Session,
        job: PlanParseJob,
        result: PlanParseResult,
        record: PlanDocument,
        status: str,
        progress: int,
    ) -> None:
        self._set_job_progress(job, result, record, status, progress)
        db.commit()

    @staticmethod
    def _set_job_progress(
        job: PlanParseJob,
        result: PlanParseResult,
        record: PlanDocument,
        status: str,
        progress: int,
    ) -> None:
        normalized_progress = max(0, min(progress, 100))
        now = datetime.utcnow()
        job.status = "running" if status == "running" else status
        job.progress = normalized_progress
        if job.started_at is None and status == "running":
            job.started_at = now
        result.parse_status = status
        result.parse_progress = normalized_progress
        record.section_parse_mode = result.section_parse_mode
        record.parse_status = status
        record.parse_progress = normalized_progress


def _sections_to_toc_lines(sections: list[ParsedSection]) -> list[str]:
    lines: list[str] = []
    for section in sections:
        lines.append(f"{'  ' * max(section.level - 1, 0)}{section.title}")
        lines.extend(_sections_to_toc_lines(section.children))
    return lines


_document_service: DocumentService | None = None


def get_document_service() -> Generator[DocumentService, None, None]:
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    yield _document_service
