from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.parsers.base import ParsedSection


SECTION_REBUILD_STRATEGIES = {
    "markdown_heading",
    "decimal_number",
    "chinese_number",
    "custom",
}


@dataclass(frozen=True)
class HeadingMatch:
    level: int
    title: str
    section_no: str | None


class SectionRebuildStrategy(Protocol):
    name: str

    def detect_heading(self, line: str) -> HeadingMatch | None:
        raise NotImplementedError


class MarkdownHeadingStrategy:
    name = "markdown_heading"

    def detect_heading(self, line: str) -> HeadingMatch | None:
        match = re.match(r"^(#{1,3})\s*(.+?)\s*#*$", line)
        if not match:
            return None
        title = match.group(2).strip()
        section_no = _extract_section_no(title)
        level = _level_from_section_no(section_no) or len(match.group(1))
        return HeadingMatch(level=min(level, 3), title=title, section_no=section_no)


class DecimalNumberStrategy:
    name = "decimal_number"

    def detect_heading(self, line: str) -> HeadingMatch | None:
        appendix = re.match(r"^\s*(附录\s*[A-Za-zＡ-Ｚ])\s+(.+)$", line)
        if appendix and _looks_like_title(line):
            section_no = re.sub(r"\s+", "", appendix.group(1))
            return HeadingMatch(level=1, title=line.strip(), section_no=section_no)

        special = re.match(r"^\s*(本标准用词说明|引用标准名录)\s*(.*)$", line)
        if special and _looks_like_title(line):
            return HeadingMatch(level=1, title=line.strip(), section_no=None)

        match = re.match(r"^\s*((?:\d{1,2}\.){1,2}\d{1,2})([\u4e00-\u9fff].*)$", line)
        if not match:
            match = re.match(r"^\s*((?:\d{1,2}\.){1,2}\d{1,2}|\d{1,2})(?:[.．、]|\s+)\s*(.+)$", line)
        if not match or not _looks_like_title(line):
            return None

        section_no = match.group(1)
        level = section_no.count(".") + 1
        if level > 3:
            return None
        return HeadingMatch(level=level, title=line.strip(), section_no=section_no)


class ChineseNumberStrategy:
    name = "chinese_number"

    def detect_heading(self, line: str) -> HeadingMatch | None:
        if not _looks_like_title(line):
            return None

        level1 = re.match(r"^\s*([一二三四五六七八九十百千万零〇两]+)[、.．]\s*(.+)$", line)
        if level1:
            return HeadingMatch(level=1, title=line.strip(), section_no=level1.group(1))

        level2 = re.match(r"^\s*[（(]([一二三四五六七八九十百千万零〇两]+)[）)]\s*(.+)$", line)
        if level2:
            return HeadingMatch(level=2, title=line.strip(), section_no=level2.group(1))

        level3 = re.match(r"^\s*[（(](\d{1,2})[）)]\s*(.+)$", line)
        if not level3:
            level3 = re.match(r"^\s*(\d{1,2})(?:[.．、]|\s+)\s*(.+)$", line)
        if level3:
            return HeadingMatch(level=3, title=line.strip(), section_no=level3.group(1))

        return None


class CustomRegexStrategy:
    name = "custom"

    def __init__(self, patterns: dict[int, str]) -> None:
        self._patterns = [
            (level, re.compile(_normalize_named_groups(pattern)))
            for level, pattern in patterns.items()
            if pattern.strip()
        ]

    def detect_heading(self, line: str) -> HeadingMatch | None:
        if not _looks_like_title(line, max_length=200):
            return None
        for level, pattern in self._patterns:
            match = pattern.match(line)
            if not match:
                continue
            groups = match.groupdict()
            title = (groups.get("title") or line).strip()
            section_no = groups.get("section_no")
            if section_no is None and match.groups():
                section_no = match.group(1)
            if section_no and groups.get("title") and not title.startswith(section_no):
                title = f"{section_no} {title}"
            return HeadingMatch(level=level, title=title, section_no=section_no)
        return None


class AutoSectionStrategy:
    name = "auto"

    def __init__(self) -> None:
        self._strategies = [
            MarkdownHeadingStrategy(),
            DecimalNumberStrategy(),
            ChineseNumberStrategy(),
        ]

    def detect_heading(self, line: str) -> HeadingMatch | None:
        for strategy in self._strategies:
            match = strategy.detect_heading(line)
            if match:
                return match
        return None


def parse_sections_with_strategy(
    markdown: str,
    strategy: str = "decimal_number",
    custom_patterns: dict[int, str] | None = None,
    use_toc_outline: bool = False,
) -> list[ParsedSection]:
    parser = get_section_rebuild_strategy(strategy, custom_patterns)
    if use_toc_outline:
        sections = _parse_sections_from_toc_outline(markdown, parser)
        if sections:
            return sections

    roots: list[ParsedSection] = []
    stack: list[ParsedSection] = []
    body_lines_before_first_heading: list[str] = []

    for raw_line in markdown.splitlines():
        line = clean_section_line(raw_line)
        if not line:
            continue

        heading = _detect_heading(parser, line)
        if heading:
            section = ParsedSection(
                level=heading.level,
                title=heading.title,
                section_no=heading.section_no,
            )
            while stack and stack[-1].level >= heading.level:
                stack.pop()
            if stack:
                stack[-1].children.append(section)
            else:
                roots.append(section)
            stack.append(section)
            continue

        if stack:
            current = stack[-1]
            current.content = f"{current.content}\n{line}".strip() if current.content else line
        else:
            body_lines_before_first_heading.append(line)

    if roots:
        if body_lines_before_first_heading:
            prefix = "\n".join(body_lines_before_first_heading).strip()
            first = roots[0]
            first.content = f"{prefix}\n{first.content}".strip() if first.content else prefix
        return roots

    text = "\n".join(clean_section_line(line) for line in markdown.splitlines()).strip()
    return [ParsedSection(level=1, title="Document", section_no=None, content=text)] if text else []


def _parse_sections_from_toc_outline(
    markdown: str,
    parser: SectionRebuildStrategy,
) -> list[ParsedSection]:
    lines = [clean_section_line(line) for line in markdown.splitlines()]
    lines = [line for line in lines if line]
    outline_parser = AutoSectionStrategy()

    for toc_index, line in enumerate(lines):
        if not _is_toc_label(line):
            continue

        outline_rows, outline_end = _collect_toc_outline_rows(lines, toc_index, outline_parser)
        if len(outline_rows) < 2:
            continue

        outline_keys = {key for _, _, _, key in outline_rows}
        body_headings = _collect_body_headings(lines, outline_end, parser, outline_keys)
        body_keys = {key for _, _, _, key in body_headings}
        matched_outline_rows = [row for row in outline_rows if row[3] in body_keys]
        if not matched_outline_rows:
            continue

        roots, flat_sections = _build_tree_from_heading_rows(matched_outline_rows)
        _fill_outline_content_from_body(lines, body_headings, flat_sections, outline_end)
        return roots

    return []


def get_section_rebuild_strategy(
    strategy: str,
    custom_patterns: dict[int, str] | None = None,
) -> SectionRebuildStrategy:
    normalized = (strategy or "decimal_number").strip().lower()
    if normalized == "auto":
        return AutoSectionStrategy()
    if normalized == "markdown_heading":
        return MarkdownHeadingStrategy()
    if normalized == "decimal_number":
        return DecimalNumberStrategy()
    if normalized == "chinese_number":
        return ChineseNumberStrategy()
    if normalized == "custom":
        patterns = custom_patterns or {}
        if not patterns:
            raise ValueError("Custom section rebuild strategy requires at least one regex pattern.")
        return CustomRegexStrategy(patterns)
    raise ValueError(f"Unsupported section rebuild strategy: {strategy}")


def _detect_heading(parser: SectionRebuildStrategy, line: str) -> HeadingMatch | None:
    heading = parser.detect_heading(line)
    if heading:
        return heading
    stripped = _strip_markdown_heading_prefix(line)
    if stripped != line:
        return parser.detect_heading(stripped)
    return None


def _collect_toc_outline_rows(
    lines: list[str],
    toc_index: int,
    parser: SectionRebuildStrategy,
) -> tuple[list[tuple[int, str, HeadingMatch, str]], int]:
    rows: list[tuple[int, str, HeadingMatch, str]] = []
    blank_or_noise_count = 0
    last_heading_index = toc_index

    for index in range(toc_index + 1, len(lines)):
        line = lines[index]
        if _is_contents_label(line):
            break
        if _is_toc_label(line):
            if rows:
                break
            continue

        heading = _detect_heading(parser, line)
        if heading and _looks_like_toc_entry(line, heading):
            heading = _clean_toc_heading(heading)
            rows.append((index, line, heading, _heading_key(heading)))
            blank_or_noise_count = 0
            last_heading_index = index
            continue

        if rows:
            blank_or_noise_count += 1
            if blank_or_noise_count >= 8:
                break

    return rows, last_heading_index + 1


def _collect_body_headings(
    lines: list[str],
    start_index: int,
    parser: SectionRebuildStrategy,
    outline_keys: set[str],
) -> list[tuple[int, str, HeadingMatch, str]]:
    rows: list[tuple[int, str, HeadingMatch, str]] = []
    fallback_parser = AutoSectionStrategy()

    for index in range(start_index, len(lines)):
        line = lines[index]
        if _is_toc_label(line) or _is_contents_label(line):
            continue
        heading = _detect_heading(parser, line) or _detect_heading(fallback_parser, line)
        if not heading:
            continue
        key = _heading_key(heading)
        if key in outline_keys:
            rows.append((index, line, heading, key))
    return rows


def _strip_markdown_heading_prefix(line: str) -> str:
    return re.sub(r"^#{1,6}\s*", "", line).strip()


def _build_tree_from_heading_rows(
    rows: list[tuple[int, str, HeadingMatch, str]],
) -> tuple[list[ParsedSection], list[tuple[ParsedSection, str]]]:
    roots: list[ParsedSection] = []
    stack: list[ParsedSection] = []
    flat_sections: list[tuple[ParsedSection, str]] = []

    for _, _, heading, key in rows:
        section = ParsedSection(
            level=heading.level,
            title=heading.title,
            section_no=heading.section_no,
        )
        while stack and stack[-1].level >= heading.level:
            stack.pop()
        if stack:
            stack[-1].children.append(section)
        else:
            roots.append(section)
        stack.append(section)
        flat_sections.append((section, key))

    return roots, flat_sections


def _fill_outline_content_from_body(
    lines: list[str],
    headings: list[tuple[int, str, HeadingMatch, str]],
    flat_sections: list[tuple[ParsedSection, str]],
    body_start: int,
) -> None:
    body_heading_by_key: dict[str, list[int]] = {}
    for index, _, _, key in headings:
        if index < body_start:
            continue
        body_heading_by_key.setdefault(key, []).append(index)

    matched_indexes: list[tuple[ParsedSection, int]] = []
    search_from = body_start
    for section, key in flat_sections:
        candidates = body_heading_by_key.get(key, [])
        match_index = next((index for index in candidates if index >= search_from), None)
        if match_index is None:
            match_index = next((index for index in candidates if index >= body_start), None)
        if match_index is None:
            continue
        matched_indexes.append((section, match_index))
        search_from = match_index + 1

    for position, (section, start_index) in enumerate(matched_indexes):
        end_index = matched_indexes[position + 1][1] if position + 1 < len(matched_indexes) else len(lines)
        content_lines = [
            _strip_markdown_heading_prefix(line)
            for line in lines[start_index + 1 : end_index]
            if line and not _is_toc_label(line)
        ]
        section.content = "\n".join(content_lines).strip()


def _find_repeated_body_start(headings: list[tuple[int, str, HeadingMatch, str]]) -> int | None:
    first_seen: dict[str, int] = {}
    for index, _, _, key in headings:
        if key in first_seen and index - first_seen[key] > 1:
            return index
        first_seen.setdefault(key, index)
    return None


def _heading_key(heading: HeadingMatch) -> str:
    title = _normalize_heading_text(heading.title)
    if heading.section_no:
        return f"{heading.section_no}:{_normalize_heading_text(_remove_section_no(title, heading.section_no))}"
    return title


def _normalize_heading_text(text: str) -> str:
    text = _strip_markdown_heading_prefix(text)
    text = _strip_toc_page_suffix(text)
    text = re.sub(r"\.{2,}\s*\d+\s*$", "", text)
    text = re.sub(r"\s+", "", text)
    return text.strip().lower()


def _remove_section_no(text: str, section_no: str) -> str:
    escaped = re.escape(section_no)
    return re.sub(rf"^\s*{escaped}\s*[.．、]?\s*", "", text).strip()


def _is_toc_label(line: str) -> bool:
    text = _strip_markdown_heading_prefix(line).strip().replace(" ", "")
    return text in {"目录", "目次"}


def _is_contents_label(line: str) -> bool:
    text = _strip_markdown_heading_prefix(line).strip().replace(" ", "").lower()
    return text == "contents"


def _looks_like_toc_entry(line: str, heading: HeadingMatch) -> bool:
    del heading
    text = _strip_markdown_heading_prefix(line).strip()
    if re.search(r"(\.{2,}|…+|\.{1}\s*\.{1}|·{2,})\s*[（(]?\d+[）)]?\s*$", text):
        return True
    if re.search(r"\s+[（(]\d+[）)]\s*$", text):
        return True
    if re.match(r"^\s*(附录\s*[A-Za-zＡ-Ｚ]|本标准用词说明|引用标准名录)\b", text):
        return True
    return False


def _clean_toc_heading(heading: HeadingMatch) -> HeadingMatch:
    return HeadingMatch(
        level=heading.level,
        title=_strip_toc_page_suffix(heading.title),
        section_no=heading.section_no,
    )


def _strip_toc_page_suffix(text: str) -> str:
    text = re.sub(r"\s*(?:\.{2,}|…+|·{2,})\s*[（(]?\d+[）)]?\s*$", "", text.strip())
    text = re.sub(r"\s+[（(]\d+[）)]\s*$", "", text)
    return text.strip()


def parse_custom_patterns(payload: dict[str, Any] | None) -> dict[int, str]:
    payload = payload or {}
    patterns: dict[int, str] = {}
    for key in ("level1_pattern", "level2_pattern", "level3_pattern"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        level = int(key[5])
        normalized = _normalize_named_groups(value)
        try:
            re.compile(normalized)
        except re.error as exc:
            raise ValueError(f"Invalid regex for {key}: {exc}") from exc
        patterns[level] = normalized
    return patterns


def clean_section_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"<a\s+id=[\"'][^\"']+[\"']\s*></a>", "", line, flags=re.IGNORECASE)
    line = re.sub(r"<!--.*?-->", "", line)
    return line.strip()


def _normalize_named_groups(pattern: str) -> str:
    return re.sub(r"\(\?<([A-Za-z_][A-Za-z0-9_]*)>", r"(?P<\1>", pattern)


def _extract_section_no(text: str) -> str | None:
    appendix_match = re.match(r"^\s*(附录\s*[A-Za-zＡ-Ｚ])\b", text)
    if appendix_match:
        return re.sub(r"\s+", "", appendix_match.group(1))

    chapter_match = re.match(r"^\s*(第[一二三四五六七八九十百千万零〇两\d]+章)", text)
    if chapter_match:
        return chapter_match.group(1)

    number_match = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?", text)
    if number_match:
        return number_match.group(1)

    chinese_match = re.match(r"^\s*([一二三四五六七八九十百千万零〇两]+)[、.．]", text)
    if chinese_match:
        return chinese_match.group(1)

    return None


def _level_from_section_no(section_no: str | None) -> int | None:
    if not section_no:
        return None
    if re.match(r"^\d{1,2}(?:\.\d{1,2}){0,2}$", section_no):
        return section_no.count(".") + 1
    if re.match(r"^第[一二三四五六七八九十百千万零〇两\d]+章$", section_no):
        return 1
    return None


def _looks_like_title(line: str, max_length: int = 120) -> bool:
    text = line.strip()
    if not text or len(text) > max_length:
        return False
    return not re.search(r"[。！？；;]$", text)
