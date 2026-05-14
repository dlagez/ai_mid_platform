from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config

    @abstractmethod
    async def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
