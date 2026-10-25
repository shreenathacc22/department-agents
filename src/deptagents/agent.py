"""The department agent loop and the orchestrator that routes to it.

The loop is written by hand so it works against any client with a messages.create method,
which keeps the tests free of network calls. Every tool call is recorded in the result.
"""

import json
from dataclasses import dataclass, field

import anthropic

from deptagents import config
from deptagents.departments import Department, build_all
from deptagents.router import Route, route
from deptagents.store import Store
from deptagents.tools import ToolError

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class ToolCall:
    name: str
    arguments: dict
    result: str
    is_error: bool = False


@dataclass
class Result:
    department: str
    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    route: Route | None = None
    stop_reason: str = "end_turn"


class DepartmentAgent:
    def __init__(self, department: Department, client, model: str | None = None, effort: str | None = None):
        self.department = department
        self.client = client
        self.model = model or config.model()
        self.effort = effort or config.effort()
        self.tools = {t.name: t for t in department.tools}
        self.history: list[dict] = []  # append-only: user, assistant, tool results

    def _create(self):
        # Claude Opus 5.5: thinking is always on, so the parameter is omitted. Effort is the dial.
        # Server-side fallback: a safety decline is re-run on the fallback model inside the same call.
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=config.MAX_TOKENS,
            system=self.department.system_prompt,
            tools=[t.to_api() for t in self.department.tools],
            messages=self.history,
            output_config={"effort": self.effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    def run_tool(self, name: str, arguments: dict) -> ToolCall:
        tool = self.tools.get(name)
        if tool is None:
            return ToolCall(name, arguments, f"Error: no tool named {name}", True)
        try:
            return ToolCall(name, arguments, tool.run(arguments))
        except ToolError as e:
            return ToolCall(name, arguments, f"Error: {e}", True)
        except Exception as e:  # a bug in a handler must not kill the conversation
            return ToolCall(name, arguments, f"Error: {type(e).__name__}: {e}", True)

    def ask(self, message: str) -> Result:
        self.history.append({"role": "user", "content": message})
        calls: list[ToolCall] = []
        for _ in range(config.MAX_TOOL_ROUNDS):
            response = self._create()
            self.history.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "refusal":
                return Result(self.department.key, "I can't help with that request.", calls, stop_reason="refusal")
            if response.stop_reason == "max_tokens":
                return Result(self.department.key, _text(response) + "\n[answer cut short]", calls, stop_reason="max_tokens")
            if response.stop_reason == "pause_turn":
                continue
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                return Result(self.department.key, _text(response), calls, stop_reason=response.stop_reason)
            results = []
            for block in tool_uses:
                arguments = block.input if isinstance(block.input, dict) else json.loads(block.input)
                call = self.run_tool(block.name, arguments)
                calls.append(call)
                item = {"type": "tool_result", "tool_use_id": block.id, "content": call.result}
                if call.is_error:
                    item["is_error"] = True
                results.append(item)
            self.history.append({"role": "user", "content": results})  # all results in one message
        return Result(self.department.key, "I stopped after too many tool calls. Please narrow the request.",
                      calls, stop_reason="tool_limit")


def _text(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


class Orchestrator:
    """Routes each request to a department agent and keeps one agent per department per session."""

    def __init__(self, client=None, store: Store | None = None, model: str | None = None, effort: str | None = None):
        self.client = client or anthropic.Anthropic()
        self.store = store or Store(state_path=config.state_path())
        self.model = model or config.model()
        self.effort = effort
        self.departments = build_all(self.store)
        self.agents: dict[str, DepartmentAgent] = {}

    def agent(self, key: str) -> DepartmentAgent:
        if key not in self.agents:
            self.agents[key] = DepartmentAgent(self.departments[key], self.client, self.model, self.effort)
        return self.agents[key]

    def handle(self, message: str, department: str | None = None) -> Result:
        if department:
            if department not in self.departments:
                raise ValueError(f"unknown department {department!r}; choose from {', '.join(self.departments)}")
            r = Route(department, 1.0, "chosen by the caller")
        else:
            r = route(self.client, message, self.departments, self.model)
        if r.department == "none" or r.department not in self.departments:
            names = ", ".join(d.title for d in self.departments.values())
            return Result("none", f"I couldn't match that to a department ({names}). {r.reason}", route=r)
        result = self.agent(r.department).ask(message)
        result.route = r
        return result
