from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.parsers.base import ParsedSection
from app.parsers.factory import ParserConfigError
from app.parsers.markdown import parse_markdown_sections


SECTION_PARSE_MODES = frozenset(
    {
        "docling_auto",
        "docling_toc_outline",
        "ppocr_toc_outline",
        "python_docx",
        "word_native",
    }
)

DEFAULT_SECTION_PARSE_MODE = "docling_auto"


class SectionParseStrategy(Protocol):
    """Build a section tree from a local file path (construction plan Word focus)."""

    name: str

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        raise NotImplementedError


class DoclingAutoSectionParseStrategy:
    """Original path: Docling -> markdown -> auto strategy, linear scan (no TOC outline)."""

    name = "docling_auto"

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        markdown = _convert_with_docling(file_path, file_name)
        return parse_markdown_sections(markdown, strategy="auto", use_toc_outline=False)


class DoclingTocOutlineSectionParseStrategy:
    """Docling -> markdown -> auto strategy with TOC outline matching."""

    name = "docling_toc_outline"

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        markdown = _convert_with_docling(file_path, file_name)
        return parse_markdown_sections(markdown, strategy="auto", use_toc_outline=True)


class PPOcrTocOutlineSectionParseStrategy:
    """PPOCR PDF -> markdown -> TOC/contents outline tree with body matching."""

    name = "ppocr_toc_outline"

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        suffix = Path(file_name).suffix.lower()
        if suffix != ".pdf":
            raise ParserConfigError(
                f"ppocr_toc_outline section parse mode supports only .pdf files; got {suffix or 'unknown'}."
            )
        from app.parsers.ppocr import PPOcrParser
        from app.parsers.section_strategy import parse_sections_from_toc_keyword_outline

        markdown = PPOcrParser().convert_to_markdown(file_path, file_name)
        sections = parse_sections_from_toc_keyword_outline(markdown, strategy="auto")
        return sections or parse_markdown_sections(markdown, strategy="auto", use_toc_outline=True)


class WordNativeSectionParseStrategy:
    """Word OOXML: heading styles + numbered fallback; skips TOC-styled paragraphs."""

    name = "word_native"

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        suffix = Path(file_name).suffix.lower()
        if suffix != ".docx":
            raise ParserConfigError(
                f"word_native section parse mode supports only .docx files; got {suffix or 'unknown'}."
            )
        from app.utils.docx_parser import parse_word_sections

        return parse_word_sections(file_path)


class PythonDocxSectionParseStrategy:
    """python-docx: heading styles + numbered fallback; removes TOC paragraphs/region."""

    name = "python_docx"

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        from app.parsers.python_docx import parse_python_docx_sections

        return parse_python_docx_sections(file_path, file_name)


_STRATEGY_BY_MODE: dict[str, SectionParseStrategy] = {
    DoclingAutoSectionParseStrategy.name: DoclingAutoSectionParseStrategy(),
    DoclingTocOutlineSectionParseStrategy.name: DoclingTocOutlineSectionParseStrategy(),
    PPOcrTocOutlineSectionParseStrategy.name: PPOcrTocOutlineSectionParseStrategy(),
    PythonDocxSectionParseStrategy.name: PythonDocxSectionParseStrategy(),
    WordNativeSectionParseStrategy.name: WordNativeSectionParseStrategy(),
}


def resolve_section_parse_mode(mode: str | None) -> str:
    normalized = (mode or "").strip().lower() or DEFAULT_SECTION_PARSE_MODE
    if normalized not in SECTION_PARSE_MODES:
        supported = ", ".join(sorted(SECTION_PARSE_MODES))
        raise ParserConfigError(
            f"Unsupported section_parse_mode: {normalized}. Supported modes: {supported}."
        )
    return normalized


def get_section_parse_strategy(mode: str) -> SectionParseStrategy:
    strategy = _STRATEGY_BY_MODE.get(mode)
    if strategy is None:
        supported = ", ".join(sorted(SECTION_PARSE_MODES))
        raise ParserConfigError(f"Unsupported section_parse_mode: {mode}. Supported modes: {supported}.")
    return strategy


def parse_construction_plan_sections(
    file_path: str,
    file_name: str,
    *,
    section_parse_mode: str | None,
    document_type: str,
) -> list[ParsedSection]:
    mode = resolve_section_parse_mode(section_parse_mode)
    return get_section_parse_strategy(mode).parse_sections(file_path, file_name)


def _convert_with_docling(file_path: str, file_name: str) -> str:
    from app.parsers.docling import DoclingParser

    return DoclingParser().convert_to_markdown(file_path, file_name)
