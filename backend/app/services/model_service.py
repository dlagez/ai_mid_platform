from pathlib import Path
from typing import Any

import yaml

from app.adapters.litellm_adapter import LiteLLMAdapter
from configs.settings import settings


class ModelService:
    def __init__(self) -> None:
        config_path = Path(settings.adapter_config_path)
        adapter_config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        litellm_config = adapter_config.get("litellm", {})
        self.adapter = LiteLLMAdapter(name="litellm", config=litellm_config)

    async def call_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.adapter.call(payload)


def get_model_service() -> ModelService:
    return ModelService()
