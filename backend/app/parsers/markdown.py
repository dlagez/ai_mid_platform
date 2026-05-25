from __future__ import annotations

from app.parsers.base import ParsedSection
from app.parsers.section_strategy import (
    clean_section_line,
    parse_sections_with_strategy,
)


def parse_markdown_sections(
    markdown: str,
    *,
    strategy: str = "auto",
    use_toc_outline: bool = False,
) -> list[ParsedSection]:
    return parse_sections_with_strategy(
        markdown,
        strategy=strategy,
        use_toc_outline=use_toc_outline,
    )


def _clean_markdown_line(line: str) -> str:
    return clean_section_line(line)
