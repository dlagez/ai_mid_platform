from __future__ import annotations

import io
import os
import tempfile
import uuid
from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import UploadFile
from minio import Minio
from sqlalchemy.orm import Session

from app.db.models import UtilityParseRecord
from app.parsers.factory import get_parser, validate_parser_file
from configs.settings import settings


class UtilityParseService:
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

    async def parse_ppocr(self, db: Session, file: UploadFile, created_by: str) -> UtilityParseRecord:
        self._ensure_bucket()
        file_name = os.path.basename(file.filename or "unnamed.pdf")
        validate_parser_file("ppocr", file_name)

        content = await file.read()
        now = datetime.now(timezone.utc)
        object_prefix = now.strftime("%Y%m%d/%H%M%S")
        object_id = uuid.uuid4().hex
        source_object_name = f"utils/ppocr/uploads/{object_prefix}_{object_id}_{file_name}"

        self._minio.put_object(
            bucket_name=self._bucket,
            object_name=source_object_name,
            data=io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/octet-stream",
        )

        record = UtilityParseRecord(
            source_file_name=file_name,
            source_file_path=f"{self._bucket}/{source_object_name}",
            source_file_size=len(content),
            source_content_type=file.content_type,
            parser_provider="ppocr",
            parse_status="parsing",
            parsed=False,
            created_by=created_by,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        tmp_path: str | None = None
        try:
            suffix = os.path.splitext(file_name)[1] or ".pdf"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            parser = get_parser("ppocr", file_name)
            markdown = parser.convert_to_markdown(tmp_path, file_name)
            markdown_bytes = markdown.encode("utf-8")
            parsed_file_name = _build_markdown_file_name(file_name, "ppocr")
            parsed_object_name = f"utils/ppocr/markdown/{object_prefix}_{object_id}_{parsed_file_name}"

            self._minio.put_object(
                bucket_name=self._bucket,
                object_name=parsed_object_name,
                data=io.BytesIO(markdown_bytes),
                length=len(markdown_bytes),
                content_type="text/markdown; charset=utf-8",
            )

            record.parsed_file_name = parsed_file_name
            record.parsed_file_path = f"{self._bucket}/{parsed_object_name}"
            record.parsed_file_size = len(markdown_bytes)
            record.parse_status = "parsed"
            record.parsed = True
            record.error_message = None
            record.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(record)
            return record
        except Exception as exc:
            db.rollback()
            record = db.query(UtilityParseRecord).filter(UtilityParseRecord.id == record.id).first()
            if record:
                record.parse_status = "failed"
                record.parsed = False
                record.error_message = str(exc)[:4000]
                record.completed_at = datetime.utcnow()
                db.commit()
                db.refresh(record)
            raise
        finally:
            if tmp_path:
                os.unlink(tmp_path)

    def list_ppocr_records(self, db: Session) -> list[UtilityParseRecord]:
        return (
            db.query(UtilityParseRecord)
            .filter(UtilityParseRecord.parser_provider == "ppocr")
            .order_by(UtilityParseRecord.created_at.desc())
            .all()
        )

    def get_record(self, db: Session, record_id: int) -> UtilityParseRecord | None:
        return db.query(UtilityParseRecord).filter(UtilityParseRecord.id == record_id).first()

    def get_markdown(self, record: UtilityParseRecord) -> str:
        if not record.parsed_file_path:
            return ""
        object_name = record.parsed_file_path.split("/", 1)[1]
        response = self._minio.get_object(self._bucket, object_name)
        try:
            return response.read().decode("utf-8", errors="replace")
        finally:
            response.close()
            response.release_conn()


def _build_markdown_file_name(file_name: str, parser_provider: str) -> str:
    base_name = os.path.basename(file_name)
    stem = os.path.splitext(base_name)[0] or "document"
    return f"{stem}-{parser_provider}-markdown.md"


_utility_parse_service: UtilityParseService | None = None


def get_utility_parse_service() -> Generator[UtilityParseService, None, None]:
    global _utility_parse_service
    if _utility_parse_service is None:
        _utility_parse_service = UtilityParseService()
    yield _utility_parse_service
