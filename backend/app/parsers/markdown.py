from __future__ import annotations

import re

from app.parsers.base import ParsedSection


def parse_markdown_sections(markdown: str) -> list[ParsedSection]:
    roots: list[ParsedSection] = []
    stack: list[ParsedSection] = []

    for raw_line in markdown.splitlines():
        line = _clean_markdown_line(raw_line)
        if not line:
            continue

        heading = _detect_heading(line)
        if heading:
            level, title, section_no = heading
            section = ParsedSection(level=level, title=title, section_no=section_no)
            while stack and stack[-1].level >= level:
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

    if roots:
        return roots

    text = "\n".join(_clean_markdown_line(line) for line in markdown.splitlines()).strip()
    return [ParsedSection(level=1, title="Document", section_no=None, content=text)] if text else []


def _clean_markdown_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"<a\s+id=[\"'][^\"']+[\"']\s*></a>", "", line, flags=re.IGNORECASE)
    line = re.sub(r"<!--.*?-->", "", line)
    return line.strip()


def _detect_heading(line: str) -> tuple[int, str, str | None] | None:
    markdown_match = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", line)
    if markdown_match:
        level = min(len(markdown_match.group(1)), 3)
        title = markdown_match.group(2).strip()
        return level, title, _extract_section_no(title)

    chapter_match = re.match(r"^\s*(第[一二三四五六七八九十百千万零〇两\d]+章)\s*(.*)$", line)
    if chapter_match:
        return 1, line.strip(), chapter_match.group(1)

    section_match = re.match(r"^\s*(第[一二三四五六七八九十百千万零〇两\d]+节)\s*(.*)$", line)
    if section_match and _looks_like_title(line):
        return 2, line.strip(), section_match.group(1)

    chinese_number_match = re.match(r"^\s*([一二三四五六七八九十]+)[、.．]\s*(.+)$", line)
    if chinese_number_match and _looks_like_title(line):
        return 2, line.strip(), chinese_number_match.group(1)

    number_match = re.match(r"^\s*((?:\d{1,2}\.){1,2}\d{1,2})([\u4e00-\u9fff].*)$", line)
    if not number_match:
        number_match = re.match(r"^\s*((?:\d{1,2}\.){1,2}\d{1,2}|\d{1,2})(?:[.．、]|\s+)\s*(.+)$", line)
    if not number_match or not _looks_like_title(line):
        return None

    section_no = number_match.group(1)
    level = section_no.count(".") + 1
    if level > 3:
        return None

    return level, line.strip(), section_no


def _extract_section_no(text: str) -> str | None:
    chapter_match = re.match(r"^\s*(第[一二三四五六七八九十百千万零〇两\d]+章)", text)
    if chapter_match:
        return chapter_match.group(1)

    number_match = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?", text)
    if number_match:
        return number_match.group(1)

    return None


def _looks_like_title(line: str) -> bool:
    text = line.strip()
    if not text or len(text) > 120:
        return False
    return not re.search(r"[。！？；;]$", text)
