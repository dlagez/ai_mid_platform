from typing import Any

from app.adapters.base_adapter import BaseAdapter


class LiteLLMAdapter(BaseAdapter):
    async def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from litellm import acompletion
        except ImportError:
            return {
                "provider": self.name,
                "model": payload["model"],
                "output": {
                    "content": "LiteLLM is not installed in this environment. Install backend requirements to enable calls.",
                },
            }

        response = await acompletion(
            model=payload["model"],
            messages=payload["messages"],
            temperature=payload.get("temperature", 0.2),
            max_tokens=payload.get("max_tokens"),
            api_base=self.config.get("api_base"),
            api_key=self.config.get("api_key"),
        )
        message: Any = response.choices[0].message
        content = message.get("content") if isinstance(message, dict) else message.content
        return {"provider": self.name, "model": payload["model"], "output": {"content": content}}
