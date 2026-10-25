"""Pick the department for a request. One short structured-output call."""

import json
from dataclasses import dataclass

from deptagents import config
from deptagents.departments import Department

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "department": {"type": "string"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["department", "confidence", "reason"],
    "additionalProperties": False,
}


@dataclass
class Route:
    department: str
    confidence: float
    reason: str


def route(client, message: str, departments: dict[str, Department], model: str | None = None) -> Route:
    menu = "\n".join(f"- {d.key}: {d.description}" for d in departments.values())
    schema = dict(ROUTE_SCHEMA)
    schema["properties"] = dict(ROUTE_SCHEMA["properties"], department={"type": "string", "enum": list(departments) + ["none"]})
    response = client.messages.create(
        model=model or config.model(),
        max_tokens=config.ROUTER_MAX_TOKENS,
        output_config={"effort": config.ROUTER_EFFORT, "format": {"type": "json_schema", "schema": schema}},
        system=("You route employee requests to one department. Answer with the department key, a confidence "
                "from 0 to 1, and a one-line reason. Use 'none' when no department fits.\n\nDepartments:\n" + menu),
        messages=[{"role": "user", "content": message}],
    )
    if response.stop_reason == "refusal":
        return Route("none", 0.0, "the request was declined")
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    data = json.loads(text)
    return Route(str(data["department"]), float(data["confidence"]), str(data["reason"]))
