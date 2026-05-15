import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


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
    import re
    m = re.search(r"toc\s*(\d+)", combined)
    if m:
        return int(m.group(1))
    return None


def _matches_heading(style_id: str, name: str) -> int | None:
    """Return heading level if this is a heading style."""
    combined = f"{style_id} {name}".lower()
    import re
    m = re.search(r"heading\s*(\d+)", combined)
    if m:
        return int(m.group(1))
    return None


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
