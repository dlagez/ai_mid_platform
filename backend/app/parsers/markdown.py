from __future__ import annotations

from app.parsers.base import ParsedSection
from app.parsers.section_strategy import (
    clean_section_line,
    parse_sections_with_strategy,
)


def parse_markdown_sections(markdown: str) -> list[ParsedSection]:
    return parse_sections_with_strategy(markdown, strategy="auto")


def _clean_markdown_line(line: str) -> str:
    return clean_section_line(line)
