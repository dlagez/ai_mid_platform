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
    "docling": {".docx", ".pdf"},
    "ppocr": {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"},
    "paddleocr": {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"},
    "paddleocr-vl": {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"},
}


def get_parser(provider: str | None = None) -> DocumentParser:
    parser_provider = (provider or settings.document_parser_provider).strip().lower()
    if parser_provider == "docling":
        return DoclingParser()
    if parser_provider in {"ppocr", "paddleocr", "paddleocr-vl"}:
        return PPOcrParser()
    raise ParserConfigError(f"Unsupported document parser provider: {parser_provider}")


def validate_parser_file(provider: str | None, file_name: str) -> None:
    parser_provider = (provider or settings.document_parser_provider).strip().lower()
    if parser_provider not in PARSER_SUPPORTED_EXTENSIONS:
        raise ParserConfigError(f"Unsupported document parser provider: {parser_provider}")

    suffix = _file_suffix(file_name)
    supported = PARSER_SUPPORTED_EXTENSIONS[parser_provider]
    if suffix not in supported:
        supported_text = ", ".join(sorted(supported))
        raise ParserUnsupportedFileError(
            f"{parser_provider} parser supports only {supported_text}; got {suffix or 'unknown file type'}."
        )


def _file_suffix(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return f".{file_name.rsplit('.', 1)[1].lower()}"
