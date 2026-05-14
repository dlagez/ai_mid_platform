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

    async def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.openkb.query(**payload)

    async def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.openkb.chat(**payload)

    async def add(self, path: str, kb_name: str | None = None) -> dict[str, Any]:
        return await self.openkb.add(path=path, kb_name=kb_name)

    def list(self, kb_name: str | None = None) -> dict[str, Any]:
        return self.openkb.list(kb_name=kb_name)

    def status(self, kb_name: str | None = None) -> dict[str, Any]:
        return self.openkb.status(kb_name=kb_name)

    def save_upload(self, filename: str, content: bytes, kb_name: str | None = None) -> Path:
        return self.openkb.save_upload(filename, content, kb_name=kb_name)


def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()
