from __future__ import annotations

from app.parsers.base import DocumentParser
from app.parsers.docling import DoclingParser
from app.parsers.ppocr import PPOcrParser
from configs.settings import settings


class ParserConfigError(ValueError):
    pass


class ParserUnsupportedFileError(ValueError):
    pass


PARSER_SUPPORTED_EXTENSIONS = {
    "docling": {".docx", ".xlsx", ".csv"},
    "ppocr": {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"},
    "paddleocr": {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"},
    "paddleocr-vl": {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"},
}

AUTO_PROVIDER_BY_EXTENSION = {
    ".docx": "docling",
    ".xlsx": "docling",
    ".csv": "docling",
    ".pdf": "ppocr",
    ".png": "ppocr",
    ".jpg": "ppocr",
    ".jpeg": "ppocr",
    ".bmp": "ppocr",
    ".tif": "ppocr",
    ".tiff": "ppocr",
    ".webp": "ppocr",
}


def get_parser(provider: str | None = None, file_name: str | None = None) -> DocumentParser:
    parser_provider = resolve_parser_provider(provider, file_name)
    if parser_provider == "docling":
        return DoclingParser()
    if parser_provider in {"ppocr", "paddleocr", "paddleocr-vl"}:
        return PPOcrParser()
    raise ParserConfigError(f"Unsupported document parser provider: {parser_provider}")


def validate_parser_file(provider: str | None, file_name: str) -> None:
    parser_provider = resolve_parser_provider(provider, file_name)
    if parser_provider not in PARSER_SUPPORTED_EXTENSIONS:
        raise ParserConfigError(f"Unsupported document parser provider: {parser_provider}")

    suffix = _file_suffix(file_name)
    supported = PARSER_SUPPORTED_EXTENSIONS[parser_provider]
    if suffix not in supported:
        supported_text = ", ".join(sorted(supported))
        raise ParserUnsupportedFileError(
            f"{parser_provider} parser supports only {supported_text}; got {suffix or 'unknown file type'}."
        )


def resolve_parser_provider(provider: str | None = None, file_name: str | None = None) -> str:
    parser_provider = (provider or "").strip().lower()
    if parser_provider:
        return parser_provider

    suffix = _file_suffix(file_name or "")
    if suffix in AUTO_PROVIDER_BY_EXTENSION:
        return AUTO_PROVIDER_BY_EXTENSION[suffix]

    return settings.document_parser_provider.strip().lower()


def _file_suffix(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return f".{file_name.rsplit('.', 1)[1].lower()}"
