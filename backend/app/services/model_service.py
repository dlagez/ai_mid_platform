from pathlib import Path
from typing import Any

import yaml

from app.core.litellm_client import LiteLLMClient
from configs.settings import settings


class ModelService:
    def __init__(self) -> None:
        config_path = Path(settings.litellm_config_path)
        litellm_config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        self.litellm = LiteLLMClient(config=litellm_config)

    async def call_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.litellm.completion(payload)


def get_model_service() -> ModelService:
    return ModelService()
