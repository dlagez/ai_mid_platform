from __future__ import annotations

import re
from typing import Any

from app.db.models import PlanSection


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = text.lower()
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.translate(str.maketrans("：，。；（）【】《》、．", ":,.;()[]<>,."))
    return normalized


def contains_any(text: str | None, keywords: list[str] | tuple[str, ...] | None) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(keyword) in normalized for keyword in _clean_keywords(keywords))


def find_section_by_title(
    sections: list[PlanSection],
    title: str,
    aliases: list[str] | tuple[str, ...] | None = None,
) -> PlanSection | None:
    title_candidates = [title, *_clean_keywords(aliases)]
    normalized_candidates = [normalize_text(item) for item in title_candidates if normalize_text(item)]

    for section in sections:
        section_title = normalize_text(section.title)
        if any(section_title == candidate for candidate in normalized_candidates):
            return section

    for section in sections:
        section_title = normalize_text(section.title)
        if any(candidate and (candidate in section_title or section_title in candidate) for candidate in normalized_candidates):
            return section

    return None


def extract_text_snippet(content: str | None, keyword: str, window: int = 80) -> str:
    if not content or not keyword:
        return ""
    index = normalize_text(content).find(normalize_text(keyword))
    if index < 0:
        raw_index = content.find(keyword)
        if raw_index < 0:
            return content[: window * 2]
        index = raw_index
    start = max(index - window, 0)
    end = min(index + len(keyword) + window, len(content))
    return content[start:end].strip()


def extract_parameter_values(content: str | None, check_object: str | None) -> list[dict[str, Any]]:
    if not content or not check_object:
        return []

    object_pattern = re.escape(check_object.strip())
    value_pattern = r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mm|毫米|m|米)?"
    pattern = re.compile(rf"{object_pattern}\s*(?:为|是|:|：)?\s*{value_pattern}", re.IGNORECASE)

    matches: list[dict[str, Any]] = []
    for match in pattern.finditer(content):
        value = float(match.group("value"))
        unit = match.group("unit") or "mm"
        matches.append(
            {
                "value": value,
                "unit": unit,
                "value_mm": normalize_unit_to_mm(value, unit),
                "snippet": content[max(match.start() - 60, 0) : min(match.end() + 60, len(content))].strip(),
            }
        )
    return matches


def compare_value(actual_mm: float, operator: str | None, threshold_mm: float) -> bool:
    normalized_operator = (operator or "").strip()
    if normalized_operator == "<=":
        return actual_mm <= threshold_mm
    if normalized_operator == ">=":
        return actual_mm >= threshold_mm
    if normalized_operator == "<":
        return actual_mm < threshold_mm
    if normalized_operator == ">":
        return actual_mm > threshold_mm
    if normalized_operator in {"=", "=="}:
        return actual_mm == threshold_mm
    return False


def normalize_unit_to_mm(value: float, unit: str | None) -> float:
    normalized_unit = (unit or "mm").strip().lower()
    if normalized_unit in {"m", "米"}:
        return value * 1000
    return value


def _clean_keywords(keywords: list[str] | tuple[str, ...] | None) -> list[str]:
    if not keywords:
        return []
    return [str(item).strip() for item in keywords if str(item).strip()]
