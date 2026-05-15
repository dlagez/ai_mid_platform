import io
import os
import tempfile
from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import UploadFile
from minio import Minio
from minio.error import S3Error
from sqlalchemy.orm import Session

from app.db.models import DocumentRecord
from app.db.session import get_db
from app.utils.docx_parser import parse_word
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
    ) -> DocumentRecord:
        self._ensure_bucket()
        content = await file.read()
        object_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{file.filename}"

        self._minio.put_object(
            bucket_name=self._bucket,
            object_name=object_name,
            data=io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/octet-stream",
        )

        record = DocumentRecord(
            file_name=file.filename or "unnamed",
            minio_path=f"{self._bucket}/{object_name}",
            uploaded_by=uploaded_by,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_files(self, db: Session) -> list[DocumentRecord]:
        return db.query(DocumentRecord).order_by(DocumentRecord.uploaded_at.desc()).all()

    def parse(self, db: Session, record_id: int) -> str:
        record = db.query(DocumentRecord).filter(DocumentRecord.id == record_id).first()
        if not record:
            raise FileNotFoundError(f"DocumentRecord id={record_id} not found")

        object_name = record.minio_path.split("/", 1)[1]
        response = self._minio.get_object(self._bucket, object_name)

        suffix = os.path.splitext(record.file_name)[1] or ".docx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(response.read())
            tmp_path = tmp.name
        try:
            return parse_word(tmp_path)
        finally:
            os.unlink(tmp_path)


_document_service: DocumentService | None = None


def get_document_service() -> Generator[DocumentService, None, None]:
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    yield _document_service
