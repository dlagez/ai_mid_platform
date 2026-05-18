import io
import os
import tempfile
from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import UploadFile
from minio import Minio
from sqlalchemy.orm import Session

from app.db.models import PlanDocument, PlanSection
from app.db.session import SessionLocal
from app.utils.docx_parser import ParsedSection, parse_word, parse_word_sections
from configs.settings import settings


class DocumentService:
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
        self, db: Session, file: UploadFile, uploaded_by: str
    ) -> PlanDocument:
        del uploaded_by
        self._ensure_bucket()
        content = await file.read()
        file_name = file.filename or "unnamed.docx"
        object_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{file_name}"

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
            parse_status="uploaded",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_files(self, db: Session) -> list[PlanDocument]:
        return db.query(PlanDocument).order_by(PlanDocument.created_at.desc()).all()

    def parse(self, db: Session, record_id: int) -> PlanDocument:
        record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
        if not record:
            raise FileNotFoundError(f"PlanDocument id={record_id} not found")

        record.parse_status = "parsing"
        db.commit()

        tmp_path: str | None = None
        try:
            tmp_path = self._download_to_temp(record)
            sections = parse_word_sections(tmp_path)
            db.query(PlanSection).filter(PlanSection.document_id == record.id).delete()
            sort_counter = 1
            for section in sections:
                sort_counter = self._insert_section_tree(db, record.id, None, section, sort_counter)
            record.parse_status = "parsed"
            db.commit()
            db.refresh(record)
            return record
        except Exception:
            db.rollback()
            record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
            if record:
                record.parse_status = "failed"
                db.commit()
            raise
        finally:
            if tmp_path:
                os.unlink(tmp_path)

    def parse_in_background(self, record_id: int) -> None:
        db = SessionLocal()
        try:
            self.parse(db, record_id)
        finally:
            db.close()

    def get_sections(self, db: Session, record_id: int) -> list[PlanSection]:
        return (
            db.query(PlanSection)
            .filter(PlanSection.document_id == record_id)
            .order_by(PlanSection.sort_no.asc())
            .all()
        )

    def get_toc_text(self, db: Session, record_id: int) -> str:
        record = db.query(PlanDocument).filter(PlanDocument.id == record_id).first()
        if not record:
            raise FileNotFoundError(f"PlanDocument id={record_id} not found")
        tmp_path = self._download_to_temp(record)
        try:
            return parse_word(tmp_path)
        finally:
            os.unlink(tmp_path)

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
        parent_id: int | None,
        parsed: ParsedSection,
        sort_no: int,
    ) -> int:
        section = PlanSection(
            document_id=document_id,
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
                section.id,
                child,
                next_sort_no,
            )
        return next_sort_no


_document_service: DocumentService | None = None


def get_document_service() -> Generator[DocumentService, None, None]:
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    yield _document_service
