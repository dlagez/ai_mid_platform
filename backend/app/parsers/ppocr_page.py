from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from configs.settings import settings


class PPOcrPageError(RuntimeError):
    pass


@dataclass
class PPOcrPageOutput:
    raw_json: dict[str, Any]
    text: str
    markdown_content: str
    rec_texts: list[str]
    rec_scores: list[float]
    rec_polys: list[Any]

    @property
    def block_count(self) -> int:
        return len(self.rec_texts)

    @property
    def average_confidence(self) -> float | None:
        scores = [score for score in self.rec_scores if isinstance(score, (int, float))]
        if not scores:
            return None
        return sum(float(score) for score in scores) / len(scores)

    @property
    def min_confidence(self) -> float | None:
        scores = [score for score in self.rec_scores if isinstance(score, (int, float))]
        if not scores:
            return None
        return min(float(score) for score in scores)


class PPOcrPageClient:
    """Calls PP-OCR page-level OCR endpoint.

    The PDF pipeline renders each page to PNG first, so the OCR service always
    receives fileType=1. The response normalizer accepts several PP-OCR shapes
    because self-hosted deployments often differ slightly between versions.
    """

    def __init__(
        self,
        base_url: str | None = None,
        ocr_endpoint: str | None = None,
        api_key: str | None = None,
        api_key_header: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._base_url = (base_url or settings.ppocr_base_url or "").rstrip("/")
        self._ocr_endpoint = ocr_endpoint or settings.ppocr_ocr_endpoint
        self._api_key = api_key if api_key is not None else settings.ppocr_api_key
        self._api_key_header = api_key_header or settings.ppocr_api_key_header
        self._timeout_seconds = timeout_seconds or settings.ppocr_page_timeout_seconds

    def ocr_png(self, png_bytes: bytes) -> PPOcrPageOutput:
        if not self._base_url:
            raise PPOcrPageError("PPOCR_BASE_URL is not configured.")

        payload = {
            "file": base64.b64encode(png_bytes).decode("ascii"),
            "fileType": 1,
        }
        raw_json = self._post_json(payload)
        return normalize_ppocr_page_response(raw_json)

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = urljoin(f"{self._base_url}/", self._ocr_endpoint.lstrip("/"))
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers[self._api_key_header] = (
                f"Bearer {self._api_key}"
                if self._api_key_header.lower() == "authorization"
                else self._api_key
            )
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise PPOcrPageError(f"PPOCR /ocr HTTP {exc.code}: {body[:500]}") from exc
        except URLError as exc:
            raise PPOcrPageError(f"PPOCR /ocr request failed: {exc.reason}") from exc


def normalize_ppocr_page_response(payload: dict[str, Any]) -> PPOcrPageOutput:
    result = payload.get("result", payload)
    rec_texts = _first_list_by_key(result, "rec_texts", "recTexts", "texts")
    rec_scores = _to_float_list(_first_list_by_key(result, "rec_scores", "recScores", "scores"))
    rec_polys = _first_list_by_key(result, "rec_polys", "recPolys", "dt_polys", "polys", "boxes")

    if not rec_texts:
        blocks = _collect_text_blocks(result)
        rec_texts = [block["text"] for block in blocks]
        rec_scores = [block["score"] for block in blocks if block.get("score") is not None]
        rec_polys = [block["poly"] for block in blocks if block.get("poly") is not None]

    markdown = _first_markdown_text(result)
    text = "\n".join(str(item) for item in rec_texts if str(item).strip())
    if not markdown:
        markdown = _texts_to_markdown(rec_texts)

    return PPOcrPageOutput(
        raw_json=payload,
        text=text,
        markdown_content=markdown,
        rec_texts=[str(item) for item in rec_texts],
        rec_scores=rec_scores,
        rec_polys=rec_polys if isinstance(rec_polys, list) else [],
    )


def _first_list_by_key(payload: Any, *keys: str) -> list[Any]:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for value in payload.values():
            found = _first_list_by_key(value, *keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _first_list_by_key(item, *keys)
            if found:
                return found
    return []


def _first_markdown_text(payload: Any) -> str:
    if isinstance(payload, dict):
        markdown = payload.get("markdown")
        if isinstance(markdown, dict) and isinstance(markdown.get("text"), str):
            return markdown["text"]
        if isinstance(markdown, str):
            return markdown
        for key in ("markdown_content", "markdownContent", "md", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        for value in payload.values():
            found = _first_markdown_text(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _first_markdown_text(item)
            if found:
                return found
    return ""


def _collect_text_blocks(payload: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        text = payload.get("text") or payload.get("block_content") or payload.get("content")
        if isinstance(text, str) and text.strip():
            score = payload.get("score") or payload.get("confidence") or payload.get("rec_score")
            poly = payload.get("poly") or payload.get("points") or payload.get("box")
            blocks.append({"text": text, "score": score if isinstance(score, (int, float)) else None, "poly": poly})
        for value in payload.values():
            blocks.extend(_collect_text_blocks(value))
    elif isinstance(payload, list):
        for item in payload:
            blocks.extend(_collect_text_blocks(item))
    return blocks


def _to_float_list(values: list[Any]) -> list[float]:
    converted: list[float] = []
    for value in values:
        try:
            converted.append(float(value))
        except (TypeError, ValueError):
            continue
    return converted


def _texts_to_markdown(texts: list[Any]) -> str:
    lines = [str(text).strip() for text in texts if str(text).strip()]
    return "\n\n".join(lines)
