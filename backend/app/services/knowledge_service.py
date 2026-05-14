from pathlib import Path
from typing import Any

import yaml

from app.adapters.openkb_adapter import OpenKBAdapter
from configs.settings import settings


class KnowledgeService:
    def __init__(self) -> None:
        config_path = Path(settings.adapter_config_path)
        adapter_config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        openkb_config = adapter_config.get("openkb", {})
        self.openkb = OpenKBAdapter(name="openkb", config=openkb_config)

    def initialize_default_kb(self) -> Path:
        return self.openkb.initialize_default_kb()

    def help(self) -> dict[str, Any]:
        return self.openkb.help()

    async def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.openkb.query(**payload)

    async def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.openkb.chat(**payload)

    async def add(self, path: str, kb_name: str | None = None) -> dict[str, Any]:
        return await self.openkb.add(path=path, kb_name=kb_name)

    def list(self, kb_name: str | None = None) -> dict[str, Any]:
        return self.openkb.list(kb_name=kb_name)

    def raw_files(self, kb_name: str | None = None) -> dict[str, Any]:
        return self.openkb.raw_files(kb_name=kb_name)

    def status(self, kb_name: str | None = None) -> dict[str, Any]:
        return self.openkb.status(kb_name=kb_name)

    def clear_session(self, kb_name: str | None = None, previous_session_id: str | None = None) -> dict[str, Any]:
        return self.openkb.clear_session(kb_name=kb_name, previous_session_id=previous_session_id)

    def save_transcript(
        self,
        session_id: str,
        kb_name: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        return self.openkb.save_transcript(session_id=session_id, kb_name=kb_name, name=name)

    async def lint(self, kb_name: str | None = None) -> dict[str, Any]:
        return await self.openkb.lint(kb_name=kb_name)

    def exit_session(self, kb_name: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        return self.openkb.exit_session(kb_name=kb_name, session_id=session_id)

    def save_upload(self, filename: str, content: bytes, kb_name: str | None = None) -> Path:
        return self.openkb.save_upload(filename, content, kb_name=kb_name)


def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()
