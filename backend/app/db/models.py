from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
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
