from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ParsedSection:
    level: int
    title: str
    section_no: str | None
    content: str = ""
    children: list["ParsedSection"] = field(default_factory=list)


class DocumentParser(Protocol):
    def parse_sections(self, file_path: str, file_name: str) -> list[ParsedSection]:
        raise NotImplementedError

    def convert_to_markdown(self, file_path: str, file_name: str) -> str:
        raise NotImplementedError
