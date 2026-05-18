from __future__ import annotations

from dataclasses import dataclass, field
import json
import mimetypes
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen
import uuid

from configs.settings import settings


@dataclass
class ParsedSection:
    level: int
    title: str
    section_no: str | None
    content: str = ""
    children: list["ParsedSection"] = field(default_factory=list)


class DoclingParseError(RuntimeError):
    pass


class DoclingParser:
    def __init__(
        self,
        base_url: str | None = None,
        convert_endpoint: str | None = None,
        legacy_convert_endpoint: str | None = None,
        file_field_name: str | None = None,
        api_key: str | None = None,
        api_key_header: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._base_url = (base_url or settings.docling_base_url or "").rstrip("/")
        self._convert_endpoint = convert_endpoint or settings.docling_convert_endpoint
        self._legacy_convert_endpoint = legacy_convert_endpoint or settings.docling_legacy_convert_endpoint
        self._file_field_name = file_field_name or settings.docling_file_field_name
        self._api_key = api_key if api_key is not None else settings.docling_api_key
        self._api_key_header = api_key_header or settings.docling_api_key_header
        self._timeout_seconds = timeout_seconds or settings.docling_timeout_seconds

    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        markdown = self.convert_to_markdown(file_path, file_name)
        return _parse_markdown_sections(markdown)

    def convert_to_markdown(self, file_path: str, file_name: str) -> str:
        if not self._base_url:
            raise DoclingParseError("DOCLING_BASE_URL is not configured.")

        errors: list[str] = []
        for endpoint in self._candidate_endpoints():
            for file_field_name in self._candidate_file_fields():
                try:
                    payload, content_type = self._encode_multipart(file_path, file_name, file_field_name)
                    response_bytes, response_content_type = self._post(endpoint, payload, content_type)
                    markdown = _extract_markdown(response_bytes, response_content_type)
                    if markdown.strip():
                        return markdown
                    errors.append(f"{endpoint}: empty conversion response")
                except HTTPError as exc:
                    body = exc.read().decode("utf-8", errors="replace")
                    errors.append(f"{endpoint}: HTTP {exc.code} {body[:300]}")
                    if exc.code not in {400, 404, 415, 422}:
                        raise DoclingParseError(errors[-1]) from exc
                except URLError as exc:
                    errors.append(f"{endpoint}: {exc.reason}")
                    raise DoclingParseError(errors[-1]) from exc

        raise DoclingParseError("; ".join(errors) or "Docling conversion failed.")

    def _candidate_endpoints(self) -> list[str]:
        endpoints = [self._convert_endpoint]
        if self._legacy_convert_endpoint and self._legacy_convert_endpoint not in endpoints:
            endpoints.append(self._legacy_convert_endpoint)
        return endpoints

    def _candidate_file_fields(self) -> list[str]:
        names = [self._file_field_name]
        for fallback in ("file", "files"):
            if fallback not in names:
                names.append(fallback)
        return names

    def _post(self, endpoint: str, payload: bytes, content_type: str) -> tuple[bytes, str]:
        url = urljoin(f"{self._base_url}/", endpoint.lstrip("/"))
        headers = {"Content-Type": content_type, "Accept": "application/json, text/markdown, text/plain"}
        if self._api_key:
            headers[self._api_key_header] = (
                f"Bearer {self._api_key}"
                if self._api_key_header.lower() == "authorization"
                else self._api_key
            )
        request = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(request, timeout=self._timeout_seconds) as response:
            return response.read(), response.headers.get("content-type", "")

    def _encode_multipart(
        self,
        file_path: str,
        file_name: str,
        file_field_name: str,
    ) -> tuple[bytes, str]:
        boundary = f"----ai-mid-platform-{uuid.uuid4().hex}"
        file_ext = os.path.splitext(file_name)[1].lower().lstrip(".")
        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        fields: list[tuple[str, str]] = [
            ("from_format", file_ext),
            ("to_formats", "md"),
            ("return_as_file", "false"),
            ("image_export_mode", "placeholder"),
            ("do_table_structure", "true"),
        ]

        body = bytearray()
        for key, value in fields:
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body.extend(f"{value}\r\n".encode())

        safe_filename = os.path.basename(file_name).encode("ascii", errors="ignore").decode() or "document"
        encoded_filename = quote(file_name)
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{file_field_name}"; '
                f'filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}\r\n'
            ).encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        with open(file_path, "rb") as f:
            body.extend(f.read())
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        return bytes(body), f"multipart/form-data; boundary={boundary}"


def _extract_markdown(response_bytes: bytes, content_type: str) -> str:
    text = response_bytes.decode("utf-8", errors="replace")
    if "json" not in content_type.lower():
        return text

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    candidates = _find_text_candidates(payload)
    markdown_candidates = [
        candidate for key, candidate in candidates if "md" in key.lower() or "markdown" in key.lower()
    ]
    if markdown_candidates:
        return "\n\n".join(markdown_candidates)

    if candidates:
        return "\n\n".join(candidate for _, candidate in candidates)

    return ""


def _find_text_candidates(payload: Any, key_path: str = "") -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{key_path}.{key}" if key_path else str(key)
            if isinstance(value, str) and key.lower() in {
                "markdown",
                "md",
                "md_content",
                "text",
                "content",
                "body",
            }:
                candidates.append((next_path, value))
            else:
                candidates.extend(_find_text_candidates(value, next_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            candidates.extend(_find_text_candidates(value, f"{key_path}[{index}]"))
    return candidates


def _parse_markdown_sections(markdown: str) -> list[ParsedSection]:
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

    number_match = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?[、\s]+(.+)$", line)
    if not number_match:
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
