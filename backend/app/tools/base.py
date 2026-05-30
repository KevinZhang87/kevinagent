from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
