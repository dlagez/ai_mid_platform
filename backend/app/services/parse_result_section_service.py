from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ParseResult, ParseResultSection
from app.parsers.base import ParsedSection
from app.parsers.section_strategy import parse_sections_with_strategy


def rebuild_parse_result_sections(
    db: Session,
    parse_result: ParseResult,
    markdown: str,
    *,
    strategy: str = "decimal_number",
    custom_patterns: dict[int, str] | None = None,
    use_toc_outline: bool = True,
) -> list[ParseResultSection]:
    """Rebuild the persisted section tree for a parse_result.

    The input Markdown may contain page anchors and page comments from the PDF
    merge step. The Markdown parser removes those markers before persisting
    section titles/content, so this table stores only parsed document text.
    """

    db.query(ParseResultSection).filter(ParseResultSection.document_id == parse_result.id).delete(
        synchronize_session=False
    )
    db.flush()

    parsed_sections = parse_sections_with_strategy(
        markdown,
        strategy=strategy,
        custom_patterns=custom_patterns,
        use_toc_outline=use_toc_outline,
    )
    sort_no = 1
    for section in parsed_sections:
        sort_no = _insert_section_tree(db, parse_result, None, section, sort_no)
    db.flush()
    return get_parse_result_sections(db, parse_result.id)


def get_parse_result_sections(db: Session, document_id: int) -> list[ParseResultSection]:
    return (
        db.query(ParseResultSection)
        .filter(ParseResultSection.document_id == document_id)
        .order_by(ParseResultSection.sort_no.asc())
        .all()
    )


def parse_result_sections_to_tree(sections: Iterable[ParseResultSection]) -> list[dict]:
    items = {
        section.id: {
            "id": section.id,
            "document_id": section.document_id,
            "job_id": section.job_id,
            "parent_id": section.parent_id,
            "title_level": section.title_level,
            "title": section.title,
            "section_no": section.section_no,
            "content": section.content,
            "sort_no": section.sort_no,
            "created_at": _dt(section.created_at),
            "children": [],
        }
        for section in sections
    }

    roots: list[dict] = []
    for section in sections:
        item = items[section.id]
        if section.parent_id and section.parent_id in items:
            items[section.parent_id]["children"].append(item)
        else:
            roots.append(item)
    return roots


def parse_result_section_to_dict(section: ParseResultSection) -> dict:
    return {
        "id": section.id,
        "document_id": section.document_id,
        "job_id": section.job_id,
        "parent_id": section.parent_id,
        "title_level": section.title_level,
        "title": section.title,
        "section_no": section.section_no,
        "content": section.content,
        "sort_no": section.sort_no,
        "created_at": _dt(section.created_at),
    }


def _insert_section_tree(
    db: Session,
    parse_result: ParseResult,
    parent_id: int | None,
    parsed: ParsedSection,
    sort_no: int,
) -> int:
    section = ParseResultSection(
        document_id=parse_result.id,
        job_id=parse_result.job_id,
        parent_id=parent_id,
        title_level=parsed.level,
        title=parsed.title,
        section_no=parsed.section_no,
        content=parsed.content,
        sort_no=sort_no,
    )
    db.add(section)
    db.flush()

    next_sort_no = sort_no + 1
    for child in parsed.children:
        next_sort_no = _insert_section_tree(db, parse_result, section.id, child, next_sort_no)
    return next_sort_no


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
