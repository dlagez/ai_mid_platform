import re
import os
from pathlib import Path
from typing import Any

import yaml

from app.core.litellm_client import LiteLLMClient
from configs.settings import settings


def _resolve_env_vars(value: str | None) -> str | None:
    """Replace ${ENV_VAR} placeholders with actual env var values."""
    if not value:
        return None

    def _replace(match: re.Match) -> str:
        return os.getenv(match.group(1), "")

    return re.sub(r"\$\{(\w+)\}", _replace, value)


class ModelService:
    def __init__(self) -> None:
        config_path = Path(settings.litellm_config_path)
        if not config_path.exists():
            self.providers: dict[str, dict[str, Any]] = {}
            self.model_map: dict[str, str] = {}
            self.default_model = "qwen3.6-plus"
            return

        raw = yaml.safe_load(config_path.read_text()) or {}
        providers = raw.get("providers", {})
        self.providers = {
            name: {
                "api_base": _resolve_env_vars(p.get("api_base")),
                "api_key": _resolve_env_vars(p.get("api_key")),
            }
            for name, p in providers.items()
        }
        self.model_map = raw.get("models", {})
        self.default_model = raw.get("default_model", "qwen-max")

    def _get_provider_for_model(self, model: str) -> str:
        return self.model_map.get(model, "dashscope")

    async def call_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = payload.get("model", self.default_model)
        provider_name = self._get_provider_for_model(model)
        provider_config = self.providers.get(provider_name, {})

        client = LiteLLMClient(config=provider_config)
        return await client.completion(payload)


def get_model_service() -> ModelService:
    return ModelService()
