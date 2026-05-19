from __future__ import annotations

import base64
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.parsers.base import ParsedSection
from app.parsers.markdown import parse_markdown_sections
from configs.settings import settings


class PPOcrParseError(RuntimeError):
    pass


class PPOcrParser:
    def __init__(
        self,
        base_url: str | None = None,
        layout_parsing_endpoint: str | None = None,
        api_key: str | None = None,
        api_key_header: str | None = None,
        timeout_seconds: int | None = None,
        format_block_content: bool | None = None,
        use_seal_recognition: bool | None = None,
        use_ocr_for_image_block: bool | None = None,
    ) -> None:
        self._base_url = (base_url or settings.ppocr_base_url or "").rstrip("/")
        self._layout_parsing_endpoint = layout_parsing_endpoint or settings.ppocr_layout_parsing_endpoint
        self._api_key = api_key if api_key is not None else settings.ppocr_api_key
        self._api_key_header = api_key_header or settings.ppocr_api_key_header
        self._timeout_seconds = timeout_seconds or settings.ppocr_timeout_seconds
        self._format_block_content = (
            format_block_content
            if format_block_content is not None
            else settings.ppocr_format_block_content
        )
        self._use_seal_recognition = (
            use_seal_recognition
            if use_seal_recognition is not None
            else settings.ppocr_use_seal_recognition
        )
        self._use_ocr_for_image_block = (
            use_ocr_for_image_block
            if use_ocr_for_image_block is not None
            else settings.ppocr_use_ocr_for_image_block
        )

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        markdown = self.convert_to_markdown(file_path, file_name)
        return parse_markdown_sections(markdown)

    def convert_to_markdown(self, file_path: str, file_name: str) -> str:
        if not self._base_url:
            raise PPOcrParseError("PPOCR_BASE_URL is not configured.")

        with open(file_path, "rb") as f:
            file_base64 = base64.b64encode(f.read()).decode("ascii")

        payload = {
            "file": file_base64,
            "fileType": 0 if file_name.lower().endswith(".pdf") else 1,
            "format_block_content": self._format_block_content,
            "use_seal_recognition": self._use_seal_recognition,
            "use_ocr_for_image_block": self._use_ocr_for_image_block,
        }
        response = self._post_json(payload)
        markdown = _extract_ppocr_markdown(response)
        if not markdown.strip():
            raise PPOcrParseError("PPOCR returned an empty markdown result.")
        return markdown

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = urljoin(f"{self._base_url}/", self._layout_parsing_endpoint.lstrip("/"))
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
            raise PPOcrParseError(f"PPOCR HTTP {exc.code}: {body[:500]}") from exc
        except URLError as exc:
            raise PPOcrParseError(f"PPOCR request failed: {exc.reason}") from exc


def _extract_ppocr_markdown(payload: dict[str, Any]) -> str:
    result = payload.get("result", payload)
    layout_results = _as_list(
        _get_any(result, "layoutParsingResults", "layout_parsing_results", "layout_parsing_result")
    )
    if not layout_results:
        layout_results = _as_list(result)

    markdown_blocks: list[str] = []
    for item in layout_results:
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                markdown_blocks.append(item)
                continue

        if not isinstance(item, dict):
            continue

        markdown = item.get("markdown")
        if isinstance(markdown, dict):
            text = markdown.get("text")
            if isinstance(text, str):
                markdown_blocks.append(text)
                continue
        elif isinstance(markdown, str):
            markdown_blocks.append(markdown)
            continue

        pruned_result = item.get("prunedResult") or item.get("pruned_result")
        if isinstance(pruned_result, dict):
            for block in _as_list(pruned_result.get("parsing_res_list")):
                if isinstance(block, dict):
                    content = block.get("block_content") or block.get("content") or block.get("text")
                    if isinstance(content, str):
                        markdown_blocks.append(content)

    return "\n\n".join(block for block in markdown_blocks if block.strip())


def _get_any(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
