"""A tool is a JSON schema plus a Python handler. The schema goes to Claude, the handler runs here."""

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    properties: dict[str, Any]
    handler: Callable[..., Any]
    required: list[str] = field(default_factory=list)

    def to_api(self) -> dict[str, Any]:
        """Strict tool definition: Claude's input always validates against this schema."""
        return {
            "name": self.name,
            "description": self.description,
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": self.required,
                "additionalProperties": False,
            },
        }

    def run(self, arguments: dict[str, Any]) -> str:
        """Call the handler and return a string for the tool_result block."""
        result = self.handler(**arguments)
        return result if isinstance(result, str) else json.dumps(result, indent=1, default=str)


class ToolError(Exception):
    """A handler refuses or fails in a way Claude should hear about (sent back with is_error)."""


def string(description: str, enum: list[str] | None = None) -> dict[str, Any]:
    prop: dict[str, Any] = {"type": "string", "description": description}
    if enum:
        prop["enum"] = enum
    return prop


def number(description: str) -> dict[str, Any]:
    return {"type": "number", "description": description}
