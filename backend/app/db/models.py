from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
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
    document_type: Mapped[str] = mapped_column(String(32), default="template", index=True)
    section_parse_mode: Mapped[str] = mapped_column(String(64), default="docling_auto", index=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    parse_progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sections: Mapped[list["PlanSection"]] = relationship(
        "PlanSection",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="PlanSection.document_id",
    )
    parse_results: Mapped[list["PlanParseResult"]] = relationship(
        "PlanParseResult",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="PlanParseResult.document_id",
    )
    parse_jobs: Mapped[list["PlanParseJob"]] = relationship(
        "PlanParseJob",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="PlanParseJob.document_id",
    )


class PlanParseResult(Base):
    __tablename__ = "plan_parse_result"
    __table_args__ = (
        UniqueConstraint("document_id", "section_parse_mode", name="uq_plan_parse_result_document_mode"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_document.id", ondelete="CASCADE"),
        index=True,
    )
    section_parse_mode: Mapped[str] = mapped_column(String(64), index=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    parse_progress: Mapped[int] = mapped_column(Integer, default=0)
    section_count: Mapped[int] = mapped_column(Integer, default=0)
    toc_text: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    document: Mapped[PlanDocument] = relationship(
        "PlanDocument",
        back_populates="parse_results",
        foreign_keys=[document_id],
    )
    sections: Mapped[list["PlanSection"]] = relationship(
        "PlanSection",
        back_populates="parse_result",
        cascade="all, delete-orphan",
        foreign_keys="PlanSection.parse_result_id",
    )


class PlanParseJob(Base):
    __tablename__ = "plan_parse_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_document.id", ondelete="CASCADE"),
        index=True,
    )
    parse_result_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("plan_parse_result.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parser_provider: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    section_parse_mode: Mapped[str] = mapped_column(String(64), index=True)
    job_type: Mapped[str] = mapped_column(String(32), default="parse", index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    document: Mapped[PlanDocument] = relationship(
        "PlanDocument",
        back_populates="parse_jobs",
        foreign_keys=[document_id],
    )
    parse_result: Mapped[PlanParseResult | None] = relationship("PlanParseResult", foreign_keys=[parse_result_id])


class PlanSection(Base):
    __tablename__ = "plan_section"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_document.id", ondelete="CASCADE"),
        index=True,
    )
    parse_result_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_parse_result.id", ondelete="CASCADE"),
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
    parse_result: Mapped[PlanParseResult] = relationship(
        "PlanParseResult",
        back_populates="sections",
        foreign_keys=[parse_result_id],
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
    ocr_endpoint: Mapped[str] = mapped_column(String(128), default="/layout-parsing")
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
    sections: Mapped[list["ParseResultSection"]] = relationship(
        "ParseResultSection",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="ParseResultSection.document_id",
    )


class ParseResultSection(Base):
    __tablename__ = "parse_result_section"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    # document_id intentionally points to parse_result.id so the section tree is
    # tied to one concrete parsed document artifact, not only the source job.
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parse_result.id", ondelete="CASCADE"),
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parse_job.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("parse_result_section.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title_level: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(512))
    section_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    sort_no: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[ParseResult] = relationship(
        "ParseResult",
        back_populates="sections",
        foreign_keys=[document_id],
    )
    job: Mapped[ParseJob] = relationship("ParseJob", foreign_keys=[job_id])
    parent: Mapped["ParseResultSection | None"] = relationship(
        "ParseResultSection",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["ParseResultSection"]] = relationship(
        "ParseResultSection",
        back_populates="parent",
        cascade="all, delete-orphan",
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


class ReviewTemplate(Base):
    __tablename__ = "review_template"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    work_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_document_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="v1.0")
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    section_rules: Mapped[list["TemplateSectionRule"]] = relationship(
        "TemplateSectionRule",
        back_populates="template",
        cascade="all, delete-orphan",
        foreign_keys="TemplateSectionRule.template_id",
    )


class TemplateSectionRule(Base):
    __tablename__ = "template_section_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("review_template.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("template_section_rule.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    section_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    standard_title: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer)
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    required_points: Mapped[list] = mapped_column(JSONB, default=list)
    min_word_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(50), default="major")
    match_strategy: Mapped[str] = mapped_column(String(50), default="title_semantic")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template: Mapped[ReviewTemplate] = relationship(
        "ReviewTemplate",
        back_populates="section_rules",
        foreign_keys=[template_id],
    )
    parent: Mapped["TemplateSectionRule | None"] = relationship(
        "TemplateSectionRule",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["TemplateSectionRule"]] = relationship(
        "TemplateSectionRule",
        back_populates="parent",
        cascade="all, delete-orphan",
    )


class StandardDocument(Base):
    __tablename__ = "standard_document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    standard_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    standard_name: Mapped[str] = mapped_column(String(255))
    standard_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    source_document_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clauses: Mapped[list["StandardClause"]] = relationship(
        "StandardClause",
        back_populates="standard",
        cascade="all, delete-orphan",
        foreign_keys="StandardClause.standard_id",
    )


class StandardClause(Base):
    __tablename__ = "standard_clause"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    standard_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("standard_document.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("standard_clause.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chapter_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    clause_no: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    applicable_work_types: Mapped[list] = mapped_column(JSONB, default=list)
    source_section_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    standard: Mapped[StandardDocument] = relationship(
        "StandardDocument",
        back_populates="clauses",
        foreign_keys=[standard_id],
    )
    parent: Mapped["StandardClause | None"] = relationship(
        "StandardClause",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["StandardClause"]] = relationship(
        "StandardClause",
        back_populates="parent",
        cascade="all, delete-orphan",
    )




class ConstructionObject(Base):
    __tablename__ = "construction_object"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    object_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    object_name: Mapped[str] = mapped_column(String(255), index=True)
    object_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("construction_object.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    related_parameters: Mapped[list] = mapped_column(JSONB, default=list)
    related_scenarios: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent: Mapped["ConstructionObject | None"] = relationship("ConstructionObject", remote_side=[id])


class ChapterReviewProfile(Base):
    __tablename__ = "chapter_review_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    evidence_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    evidence_text: Mapped[str] = mapped_column(Text)
    object_terms: Mapped[list] = mapped_column(JSONB, default=list)
    task_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("review_task.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_document.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_section.id", ondelete="CASCADE"), index=True)
    chapter_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chapter_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task: Mapped["ReviewTask | None"] = relationship("ReviewTask", foreign_keys=[task_id])
    document: Mapped[PlanDocument] = relationship("PlanDocument", foreign_keys=[document_id])
    section: Mapped[PlanSection] = relationship("PlanSection", foreign_keys=[section_id])


class ChapterProfileGenerationJob(Base):
    __tablename__ = "chapter_profile_generation_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_document.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("review_task.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    total_sections: Mapped[int] = mapped_column(Integer, default=0)
    processed_sections: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    rule_only_count: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document: Mapped[PlanDocument] = relationship("PlanDocument", foreign_keys=[document_id])
    task: Mapped["ReviewTask | None"] = relationship("ReviewTask", foreign_keys=[task_id])
    items: Mapped[list["ChapterProfileGenerationItem"]] = relationship(
        "ChapterProfileGenerationItem",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="ChapterProfileGenerationItem.job_id",
    )


class ChapterProfileGenerationItem(Base):
    __tablename__ = "chapter_profile_generation_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chapter_profile_generation_job.id", ondelete="CASCADE"),
        index=True,
    )
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_document.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plan_section.id", ondelete="SET NULL"), nullable=True, index=True)
    section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    profile_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chapter_review_profile.id", ondelete="SET NULL"), nullable=True, index=True)
    used_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job: Mapped[ChapterProfileGenerationJob] = relationship(
        "ChapterProfileGenerationJob",
        back_populates="items",
        foreign_keys=[job_id],
    )
    document: Mapped[PlanDocument] = relationship("PlanDocument", foreign_keys=[document_id])
    section: Mapped[PlanSection | None] = relationship("PlanSection", foreign_keys=[section_id])
    profile: Mapped[ChapterReviewProfile | None] = relationship("ChapterReviewProfile", foreign_keys=[profile_id])


class ReviewCheckpoint(Base):
    __tablename__ = "review_checkpoint"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    rule_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    rule_text: Mapped[str] = mapped_column(Text)
    object_terms: Mapped[list] = mapped_column(JSONB, default=list)
    standard_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("standard_document.id"), nullable=True, index=True)
    clause_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("standard_clause.id"), nullable=True, index=True)
    clause_no: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    clause_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewCheckpointGenerationJob(Base):
    __tablename__ = "review_checkpoint_generation_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    standard_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("standard_document.id", ondelete="SET NULL"), nullable=True, index=True)
    clause_ids: Mapped[list] = mapped_column(JSONB, default=list)
    use_llm: Mapped[bool] = mapped_column(Boolean, default=True)
    concurrency: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    total_clauses: Mapped[int] = mapped_column(Integer, default=0)
    processed_clauses: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint_ids: Mapped[list] = mapped_column(JSONB, default=list)
    failed: Mapped[list] = mapped_column(JSONB, default=list)
    skipped: Mapped[list] = mapped_column(JSONB, default=list)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    standard: Mapped[StandardDocument | None] = relationship("StandardDocument", foreign_keys=[standard_id])
    items: Mapped[list["ReviewCheckpointGenerationItem"]] = relationship(
        "ReviewCheckpointGenerationItem",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="ReviewCheckpointGenerationItem.job_id",
    )


class ReviewCheckpointGenerationItem(Base):
    __tablename__ = "review_checkpoint_generation_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("review_checkpoint_generation_job.id", ondelete="CASCADE"),
        index=True,
    )
    standard_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("standard_document.id", ondelete="SET NULL"), nullable=True, index=True)
    clause_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("standard_clause.id", ondelete="SET NULL"), nullable=True, index=True)
    clause_no: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    clause_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    checkpoint_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job: Mapped[ReviewCheckpointGenerationJob] = relationship(
        "ReviewCheckpointGenerationJob",
        back_populates="items",
        foreign_keys=[job_id],
    )
    standard: Mapped[StandardDocument | None] = relationship("StandardDocument", foreign_keys=[standard_id])
    clause: Mapped[StandardClause | None] = relationship("StandardClause", foreign_keys=[clause_id])


class CheckpointMatchResult(Base):
    __tablename__ = "checkpoint_match_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("review_task.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_section.id", ondelete="CASCADE"), index=True)
    checkpoint_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("review_checkpoint.id", ondelete="CASCADE"), index=True)
    match_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_dimensions: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="candidate", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task: Mapped["ReviewTask"] = relationship("ReviewTask", foreign_keys=[task_id])
    section: Mapped[PlanSection] = relationship("PlanSection", foreign_keys=[section_id])
    checkpoint: Mapped[ReviewCheckpoint] = relationship("ReviewCheckpoint", foreign_keys=[checkpoint_id])


class ReviewTask(Base):
    __tablename__ = "review_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    task_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan_document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_document.id", ondelete="CASCADE"),
        index=True,
    )
    template_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("review_template.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    work_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    review_mode: Mapped[str] = mapped_column(String(50), default="standard")
    status: Mapped[str] = mapped_column(String(50), default="created", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    major_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    minor_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[PlanDocument] = relationship("PlanDocument", foreign_keys=[plan_document_id])
    template: Mapped[ReviewTemplate | None] = relationship("ReviewTemplate", foreign_keys=[template_id])
    execution_logs: Mapped[list["RuleExecutionLog"]] = relationship(
        "RuleExecutionLog",
        back_populates="task",
        cascade="all, delete-orphan",
        foreign_keys="RuleExecutionLog.task_id",
    )


class RuleExecutionLog(Base):
    __tablename__ = "rule_execution_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("review_task.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    rule_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    rule_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    template_rule_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    plan_section_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("plan_section.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    task: Mapped[ReviewTask] = relationship("ReviewTask", back_populates="execution_logs", foreign_keys=[task_id])
    section: Mapped[PlanSection | None] = relationship("PlanSection", foreign_keys=[plan_section_id])
