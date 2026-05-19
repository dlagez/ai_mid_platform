from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TaskRecord(Base):
    __tablename__ = "task_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    task_type: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentRecord(Base):
    __tablename__ = "document_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(256))
    minio_path: Mapped[str] = mapped_column(String(512))
    uploaded_by: Mapped[str] = mapped_column(String(128))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PlanDocument(Base):
    __tablename__ = "plan_document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(256))
    file_path: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(BigInteger)
    parse_status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sections: Mapped[list["PlanSection"]] = relationship(
        "PlanSection",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="PlanSection.document_id",
    )


class PlanSection(Base):
    __tablename__ = "plan_section"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_document.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("plan_section.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    level: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(512))
    section_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    sort_no: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[PlanDocument] = relationship(
        "PlanDocument",
        back_populates="sections",
        foreign_keys=[document_id],
    )
    parent: Mapped["PlanSection | None"] = relationship(
        "PlanSection",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["PlanSection"]] = relationship(
        "PlanSection",
        back_populates="parent",
        cascade="all, delete-orphan",
    )


class UtilityParseRecord(Base):
    __tablename__ = "utility_parse_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    source_file_name: Mapped[str] = mapped_column(String(256))
    source_file_path: Mapped[str] = mapped_column(String(512))
    source_file_size: Mapped[int] = mapped_column(BigInteger)
    source_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parsed_file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    parsed_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parsed_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    parser_provider: Mapped[str] = mapped_column(String(64), index=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    parsed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ParseJob(Base):
    __tablename__ = "parse_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    file_id: Mapped[str] = mapped_column(String(64), index=True)
    file_name: Mapped[str] = mapped_column(String(256))
    file_size: Mapped[int] = mapped_column(BigInteger)
    file_hash: Mapped[str] = mapped_column(String(128), index=True)
    page_count: Mapped[int] = mapped_column(Integer)
    source_file_path: Mapped[str] = mapped_column(String(512))
    parser_provider: Mapped[str] = mapped_column(String(64), default="ppocr", index=True)
    parse_mode: Mapped[str] = mapped_column(String(64), default="page_ocr")
    ocr_endpoint: Mapped[str] = mapped_column(String(128), default="/ocr")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    dpi: Mapped[int] = mapped_column(Integer, default=180)
    batch_size: Mapped[int] = mapped_column(Integer, default=10)
    page_timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.75)
    low_confidence_flag: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_pages: Mapped[int] = mapped_column(Integer, default=0)
    failed_pages: Mapped[int] = mapped_column(Integer, default=0)
    low_confidence_pages: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    parse_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_markdown_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_json_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_result_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pages: Mapped[list["ParsePageResult"]] = relationship(
        "ParsePageResult",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="ParsePageResult.job_id",
    )
    result: Mapped["ParseResult | None"] = relationship(
        "ParseResult",
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
        foreign_keys="ParseResult.job_id",
    )


class ParsePageResult(Base):
    __tablename__ = "parse_page_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parse_job.id", ondelete="CASCADE"), index=True)
    page_no: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_json_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    markdown_content: Mapped[str] = mapped_column(Text, default="")
    rec_texts: Mapped[list] = mapped_column(JSON, default=list)
    rec_scores: Mapped[list] = mapped_column(JSON, default=list)
    rec_polys: Mapped[list] = mapped_column(JSON, default=list)
    average_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    low_confidence_flag: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped[ParseJob] = relationship(
        "ParseJob",
        back_populates="pages",
        foreign_keys=[job_id],
    )


class ParseResult(Base):
    __tablename__ = "parse_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parse_job.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    markdown_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    json_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_result_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    markdown_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    json_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_pages: Mapped[int] = mapped_column(Integer, default=0)
    failed_pages: Mapped[int] = mapped_column(Integer, default=0)
    low_confidence_pages: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    parse_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[ParseJob] = relationship(
        "ParseJob",
        back_populates="result",
        foreign_keys=[job_id],
    )


class DocumentMarkdownMap(Base):
    __tablename__ = "document_markdown_map"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parse_job.id", ondelete="CASCADE"), index=True)
    page_result_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parse_page_result.id", ondelete="CASCADE"),
        index=True,
    )
    page_no: Mapped[int] = mapped_column(Integer, index=True)
    markdown_start: Mapped[int] = mapped_column(Integer)
    markdown_end: Mapped[int] = mapped_column(Integer)
    anchor: Mapped[str] = mapped_column(String(64))
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
