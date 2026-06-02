from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.db.models import ParseResult, ParseResultSection, StandardClause, StandardDocument
from app.standards.schemas import (
    ImportStandardFromDocumentRequest,
    StandardClauseCreate,
    StandardClauseUpdate,
    StandardDocumentCreate,
    StandardDocumentUpdate,
)
from app.utils.exceptions import PlatformError

STANDARD_STATUSES = {"draft", "active", "disabled", "archived"}
STANDARD_TYPES = {"national", "industry", "local", "enterprise", "other"}
MANDATORY_TERMS = ("必须", "严禁", "不得", "应当")


class StandardService:
    def list_standards(self, db: Session) -> tuple[list[StandardDocument], int]:
        query = db.query(StandardDocument).filter(StandardDocument.status != "archived")
        return query.order_by(StandardDocument.created_at.desc()).all(), query.count()

    def get_standard(self, db: Session, standard_id: int) -> StandardDocument:
        standard = db.query(StandardDocument).filter(StandardDocument.id == standard_id).first()
        if not standard or standard.status == "archived":
            raise PlatformError(f"Standard document id={standard_id} not found", status_code=404)
        return standard

    def create_standard(
        self,
        db: Session,
        data: StandardDocumentCreate,
        created_by: int | None = None,
    ) -> StandardDocument:
        self._validate_standard_values(data.status, data.standard_type)
        standard = StandardDocument(**data.model_dump(), created_by=created_by)
        db.add(standard)
        db.commit()
        db.refresh(standard)
        return standard

    def update_standard(self, db: Session, standard_id: int, data: StandardDocumentUpdate) -> StandardDocument:
        standard = self.get_standard(db, standard_id)
        values = data.model_dump(exclude_unset=True)
        self._validate_standard_values(values.get("status"), values.get("standard_type"))
        for key, value in values.items():
            setattr(standard, key, value)
        db.commit()
        db.refresh(standard)
        return standard

    def archive_standard(self, db: Session, standard_id: int) -> StandardDocument:
        standard = self.get_standard(db, standard_id)
        standard.status = "archived"
        db.commit()
        db.refresh(standard)
        return standard

    def import_from_document(
        self,
        db: Session,
        data: ImportStandardFromDocumentRequest,
        created_by: int | None = None,
    ) -> tuple[StandardDocument, int]:
        parse_result: ParseResult | None = None
        sections: list[ParseResultSection] = []
        if data.document_id:
            parse_result = db.query(ParseResult).filter(ParseResult.id == data.document_id).first()
            if not parse_result:
                raise PlatformError(f"Parse result id={data.document_id} not found", status_code=404)

            sections = (
                db.query(ParseResultSection)
                .filter(ParseResultSection.document_id == parse_result.id)
                .order_by(ParseResultSection.sort_no.asc())
                .all()
            )
            if not sections:
                raise PlatformError("The selected parse result has no parsed sections.", status_code=400)

        self._validate_standard_values("draft", data.standard_type)
        standard = StandardDocument(
            standard_code=data.standard_code,
            standard_name=data.standard_name,
            standard_type=data.standard_type,
            version=data.version,
            effective_date=data.effective_date,
            source_file_id=parse_result.job_id if parse_result else None,
            source_document_id=parse_result.id if parse_result else None,
            status="draft",
            description=data.description,
            created_by=created_by,
        )
        db.add(standard)
        db.flush()

        clause_count = self.sync_clauses_from_parse_result(db, standard, sections)

        db.commit()
        db.refresh(standard)
        return standard, clause_count

    def sync_clauses_from_parse_result(
        self,
        db: Session,
        standard: StandardDocument,
        sections: list[ParseResultSection] | None = None,
    ) -> int:
        if not standard.source_document_id:
            return 0
        if sections is None:
            sections = (
                db.query(ParseResultSection)
                .filter(ParseResultSection.document_id == standard.source_document_id)
                .order_by(ParseResultSection.sort_no.asc())
                .all()
            )
        if not sections:
            return 0

        existing_clauses = (
            db.query(StandardClause)
            .filter(StandardClause.standard_id == standard.id)
            .order_by(StandardClause.order_no.asc(), StandardClause.id.asc())
            .all()
        )
        existing_by_source_id = {
            clause.source_section_id: clause
            for clause in existing_clauses
            if clause.source_section_id is not None
        }
        existing_by_order_no = {clause.order_no: clause for clause in existing_clauses}
        section_map = {section.id: section for section in sections}
        clause_id_map: dict[int, int] = {}
        for section in sections:
            content = section.content or ""
            clause = existing_by_source_id.get(section.id) or existing_by_order_no.get(section.sort_no)
            values = {
                "standard_id": standard.id,
                "parent_id": clause_id_map.get(section.parent_id) if section.parent_id else None,
                "chapter_no": self._chapter_no(section.section_no),
                "clause_no": section.section_no,
                "title": section.title[:255] if section.title else None,
                "content": content,
                "level": section.title_level,
                "path": self._build_section_path(section, section_map),
                "is_mandatory": self._looks_mandatory(content),
                "source_section_id": section.id,
                "order_no": section.sort_no,
            }
            if clause:
                for key, value in values.items():
                    setattr(clause, key, value)
            else:
                clause = StandardClause(
                    **values,
                    keywords=[],
                    applicable_work_types=[],
                )
                db.add(clause)
            db.flush()
            clause_id_map[section.id] = clause.id

        active_source_ids = {section.id for section in sections}
        for clause in existing_clauses:
            if clause.source_section_id not in active_source_ids and clause.order_no not in {section.sort_no for section in sections}:
                db.delete(clause)
        db.flush()
        return len(sections)

    def sync_clauses_from_parse_result_for_document(
        self,
        db: Session,
        parse_result_id: int,
        sections: list[ParseResultSection] | None = None,
    ) -> int:
        standards = (
            db.query(StandardDocument)
            .filter(
                StandardDocument.source_document_id == parse_result_id,
                StandardDocument.status != "archived",
            )
            .order_by(StandardDocument.id.asc())
            .all()
        )
        synced = 0
        for standard in standards:
            self.sync_clauses_from_parse_result(db, standard, sections)
            synced += 1
        return synced

    def list_clauses(
        self,
        db: Session,
        standard_id: int,
        *,
        keyword: str | None = None,
        clause_no: str | None = None,
        is_mandatory: bool | None = None,
        work_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[StandardClause], int]:
        self.get_standard(db, standard_id)
        query = db.query(StandardClause).filter(StandardClause.standard_id == standard_id)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(or_(StandardClause.title.ilike(like), StandardClause.content.ilike(like)))
        if clause_no:
            query = query.filter(StandardClause.clause_no.ilike(f"%{clause_no}%"))
        if is_mandatory is not None:
            query = query.filter(StandardClause.is_mandatory == is_mandatory)
        if work_type:
            query = query.filter(cast(StandardClause.applicable_work_types, String).ilike(f"%{work_type}%"))
        total = query.count()
        items = (
            query.order_by(StandardClause.order_no.asc(), StandardClause.id.asc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_clause(self, db: Session, clause_id: int) -> StandardClause:
        clause = db.query(StandardClause).filter(StandardClause.id == clause_id).first()
        if not clause:
            raise PlatformError(f"Standard clause id={clause_id} not found", status_code=404)
        return clause

    def create_clause(self, db: Session, standard_id: int, data: StandardClauseCreate) -> StandardClause:
        self.get_standard(db, standard_id)
        if data.parent_id:
            self._get_clause_for_standard(db, data.parent_id, standard_id)
        clause = StandardClause(standard_id=standard_id, **data.model_dump())
        db.add(clause)
        db.commit()
        db.refresh(clause)
        return clause

    def update_clause(self, db: Session, clause_id: int, data: StandardClauseUpdate) -> StandardClause:
        clause = self.get_clause(db, clause_id)
        values = data.model_dump(exclude_unset=True)
        parent_id = values.get("parent_id")
        if parent_id:
            parent = self._get_clause_for_standard(db, parent_id, clause.standard_id)
            if parent.id == clause.id:
                raise PlatformError("A clause cannot be its own parent.", status_code=400)
        for key, value in values.items():
            setattr(clause, key, value)
        db.commit()
        db.refresh(clause)
        return clause

    def delete_clause(self, db: Session, clause_id: int) -> StandardClause:
        clause = self.get_clause(db, clause_id)
        db.delete(clause)
        db.commit()
        return clause

    def _get_clause_for_standard(self, db: Session, clause_id: int, standard_id: int) -> StandardClause:
        clause = (
            db.query(StandardClause)
            .filter(StandardClause.id == clause_id, StandardClause.standard_id == standard_id)
            .first()
        )
        if not clause:
            raise PlatformError(f"Standard clause id={clause_id} not found", status_code=404)
        return clause

    def _validate_standard_values(self, status: str | None, standard_type: str | None) -> None:
        if status and status not in STANDARD_STATUSES:
            raise PlatformError(f"Invalid standard status: {status}", status_code=400)
        if standard_type and standard_type not in STANDARD_TYPES:
            raise PlatformError(f"Invalid standard type: {standard_type}", status_code=400)

    def _looks_mandatory(self, content: str) -> bool:
        return any(term in content for term in MANDATORY_TERMS)

    def _chapter_no(self, section_no: str | None) -> str | None:
        if not section_no:
            return None
        return section_no.split(".", 1)[0]

    def _build_section_path(self, section: ParseResultSection, section_map: dict[int, ParseResultSection]) -> str:
        parts: list[str] = []
        current: ParseResultSection | None = section
        while current:
            parts.append(current.section_no or current.title)
            current = section_map.get(current.parent_id) if current.parent_id else None
        return " / ".join(reversed([part for part in parts if part]))


def get_standard_service() -> Generator[StandardService, None, None]:
    yield StandardService()
