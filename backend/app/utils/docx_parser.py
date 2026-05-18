from dataclasses import dataclass, field
import re
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class ParsedSection:
    level: int
    title: str
    section_no: str | None
    content: str = ""
    children: list["ParsedSection"] = field(default_factory=list)


def parse_word(file_path: str) -> str:
    """Extract and return the Table of Contents text from a Word document."""
    styles = _load_styles(file_path)

    toc_text = _extract_toc_entries(file_path, styles)
    if toc_text:
        return toc_text

    heading_text = _extract_headings(file_path, styles)
    if heading_text:
        return heading_text

    return ""


def parse_word_sections(file_path: str) -> list[ParsedSection]:
    """Parse a docx into a chapter tree with section body content."""
    styles = _load_styles(file_path)
    paragraphs = _extract_paragraphs(file_path, styles)
    if not paragraphs:
        return []

    native_headings = [
        (text, level)
        for text, style_id, style_name in paragraphs
        if text and (level := _matches_heading(style_id or "", style_name or "")) in {1, 2, 3}
    ]
    use_native_headings = bool(native_headings)

    roots: list[ParsedSection] = []
    stack: list[ParsedSection] = []

    for text, style_id, style_name in paragraphs:
        if not text:
            continue

        heading = _detect_heading(text, style_id or "", style_name or "", use_native_headings)
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
            current.content = f"{current.content}\n{text}".strip() if current.content else text

    return roots


def _load_styles(file_path: str) -> dict[str, str]:
    """Return mapping of styleId -> style name from styles.xml."""
    mapping: dict[str, str] = {}
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            if "word/styles.xml" not in z.namelist():
                return mapping
            with z.open("word/styles.xml") as f:
                tree = ET.parse(f)
                for style in tree.iter(f"{NS}style"):
                    style_id = style.get(f"{NS}styleId")
                    name_el = style.find(f"{NS}name")
                    name = name_el.get(f"{NS}val") if name_el is not None else ""
                    if style_id:
                        mapping[style_id] = name
    except Exception:
        pass
    return mapping


def _matches_toc(style_id: str, name: str) -> int | None:
    """Return TOC level if this style is a TOC entry style (e.g. 'toc 1', 'TOC1')."""
    combined = f"{style_id} {name}".lower()
    if "toc heading" in combined:
        return 0
    m = re.search(r"toc\s*(\d+)", combined)
    if m:
        return int(m.group(1))
    return None


def _matches_heading(style_id: str, name: str) -> int | None:
    """Return heading level if this is a heading style."""
    combined = f"{style_id} {name}".lower()
    m = re.search(r"heading\s*(\d+)", combined)
    if m and int(m.group(1)) <= 3:
        return int(m.group(1))

    title_match = re.search(r"标题\s*(\d+)", f"{style_id} {name}")
    if title_match and int(title_match.group(1)) <= 3:
        return int(title_match.group(1))

    if "标题" in name and style_id in {"1", "2", "3"}:
        return int(style_id)

    return None


def _detect_heading(
    text: str,
    style_id: str,
    style_name: str,
    use_native_headings: bool,
) -> tuple[int, str, str | None] | None:
    if use_native_headings:
        level = _matches_heading(style_id, style_name)
        if level in {1, 2, 3}:
            return level, text, _extract_section_no(text)
        return None

    fallback = _matches_numbered_heading(text)
    if fallback:
        return fallback

    return None


def _matches_numbered_heading(text: str) -> tuple[int, str, str | None] | None:
    chapter_match = re.match(r"^\s*(第[一二三四五六七八九十百千万零〇两\d]+章)\s*(.*)$", text)
    if chapter_match:
        return 1, text.strip(), chapter_match.group(1)

    number_match = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?[、\s]*(.*)$", text)
    if not number_match:
        return None

    section_no = number_match.group(1)
    if not number_match.group(2).strip():
        return None

    level = section_no.count(".") + 1
    if level > 3:
        return None

    return level, text.strip(), section_no


def _extract_section_no(text: str) -> str | None:
    chapter_match = re.match(r"^\s*(第[一二三四五六七八九十百千万零〇两\d]+章)", text)
    if chapter_match:
        return chapter_match.group(1)

    number_match = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?", text)
    if number_match:
        return number_match.group(1)

    return None


def _extract_paragraphs(
    file_path: str,
    styles: dict[str, str],
) -> list[tuple[str, str | None, str | None]]:
    paragraphs: list[tuple[str, str | None, str | None]] = []
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            if "word/document.xml" not in z.namelist():
                return []
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                for para in tree.iter(f"{NS}p"):
                    text = _para_text(para)
                    style_id = _para_style_id(para)
                    style_name = styles.get(style_id, "") if style_id else ""
                    paragraphs.append((text, style_id, style_name))
    except Exception:
        return []
    return paragraphs


def _extract_toc_entries(file_path: str, styles: dict[str, str]) -> str:
    """Extract paragraphs whose style is a TOC entry style."""
    entries: list[str] = []
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            if "word/document.xml" not in z.namelist():
                return ""
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                for para in tree.iter(f"{NS}p"):
                    style_id = _para_style_id(para)
                    if not style_id:
                        continue
                    name = styles.get(style_id, "")
                    level = _matches_toc(style_id, name)
                    if level is None:
                        continue
                    text = _para_text(para)
                    if not text:
                        continue
                    if level == 0:
                        entries.insert(0, text)
                    else:
                        indent = "  " * (level - 1)
                        entries.append(f"{indent}{text}")
    except Exception:
        pass
    return "\n".join(entries)


def _extract_headings(file_path: str, styles: dict[str, str]) -> str:
    """Fallback: extract heading paragraphs."""
    entries: list[str] = []
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            if "word/document.xml" not in z.namelist():
                return ""
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                for para in tree.iter(f"{NS}p"):
                    style_id = _para_style_id(para)
                    if not style_id:
                        continue
                    name = styles.get(style_id, "")
                    level = _matches_heading(style_id, name)
                    if level is None:
                        continue
                    text = _para_text(para)
                    if not text:
                        continue
                    indent = "  " * (level - 1)
                    entries.append(f"{indent}{text}")
    except Exception:
        pass
    return "\n".join(entries)


def _para_style_id(para: ET.Element) -> str | None:
    style_el = para.find(f"./{NS}pPr/{NS}pStyle")
    if style_el is not None:
        return style_el.get(f"{NS}val")
    return None


def _para_text(para: ET.Element) -> str:
    texts = [t.text or "" for t in para.iter(f"{NS}t")]
    return "".join(texts).strip()
