"""A stand-in for anthropic.Anthropic that replays scripted responses. No network."""

import json
from types import SimpleNamespace


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(name, arguments, block_id="toolu_1"):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=arguments)


def message(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def route_message(department, confidence=0.9, reason="matches"):
    return message([text_block(json.dumps({"department": department, "confidence": confidence, "reason": reason}))])


class _Messages:
    def __init__(self, script, log):
        self.script, self.log = script, log

    def create(self, **kwargs):
        self.log.append(kwargs)
        if not self.script:
            raise AssertionError("fake client ran out of scripted responses")
        return self.script.pop(0)


class FakeClient:
    """script: responses in the order the code will ask for them, across router and agent calls."""

    def __init__(self, script):
        self.calls = []
        self.messages = _Messages(script, self.calls)
        self.beta = SimpleNamespace(messages=self.messages)
