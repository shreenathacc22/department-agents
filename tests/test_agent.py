import json

import pytest

from deptagents.agent import FALLBACK_BETA, DepartmentAgent, Orchestrator
from fake_client import FakeClient, message, route_message, text_block, tool_use_block


def test_agent_runs_a_tool_and_feeds_the_result_back(store):
    client = FakeClient([
        message([text_block("Let me check."), tool_use_block("get_leave_balance", {"employee_id": "E-1001"}, "toolu_a")], "tool_use"),
        message([text_block("You have 14 annual days left.")]),
    ])
    orch = Orchestrator(client=client, store=store)
    r = orch.handle("how much leave do I have? I'm E-1001", department="hr")
    assert r.department == "hr" and r.answer == "You have 14 annual days left."
    assert [c.name for c in r.tool_calls] == ["get_leave_balance"]
    assert json.loads(r.tool_calls[0].result)["balances_days"]["annual"] == 14
    # request shape
    first, second = client.calls
    assert first["model"] == "claude-opus-5-5"
    assert first["betas"] == [FALLBACK_BETA] and first["fallbacks"] == "default"
    assert first["output_config"] == {"effort": "medium"}
    assert "thinking" not in first
    assert [t["name"] for t in first["tools"]] == ["get_leave_balance", "request_leave", "lookup_hr_policy"]
    assert all(t["strict"] for t in first["tools"])
    # the second request carries the assistant turn and one user message holding the tool result
    msgs = second["messages"]
    assert msgs[1]["role"] == "assistant" and msgs[2]["role"] == "user"
    assert msgs[2]["content"][0] == {"type": "tool_result", "tool_use_id": "toolu_a", "content": r.tool_calls[0].result}


def test_tool_error_goes_back_with_is_error(store):
    client = FakeClient([
        message([tool_use_block("get_leave_balance", {"employee_id": "E-404"})], "tool_use"),
        message([text_block("That id does not exist.")]),
    ])
    r = Orchestrator(client=client, store=store).handle("leave for E-404", department="hr")
    assert r.tool_calls[0].is_error and "no employee" in r.tool_calls[0].result
    assert client.calls[1]["messages"][2]["content"][0]["is_error"] is True


def test_parallel_tool_calls_return_in_one_message(store):
    client = FakeClient([
        message([tool_use_block("check_system_status", {"system": "vpn"}, "t1"),
                 tool_use_block("search_knowledge_base", {"query": "vpn"}, "t2")], "tool_use"),
        message([text_block("VPN east gateway is slow; use west. Here is how to connect.")]),
    ])
    r = Orchestrator(client=client, store=store).handle("vpn is slow, how do I connect", department="it")
    assert len(r.tool_calls) == 2
    results = client.calls[1]["messages"][2]["content"]
    assert [x["tool_use_id"] for x in results] == ["t1", "t2"]


def test_router_then_agent_and_sessions_are_per_department(store):
    client = FakeClient([
        route_message("finance", 0.95, "expense claim"),
        message([tool_use_block("submit_expense", {"employee_id": "E-1002", "amount": 30, "category": "meals", "description": "lunch"})], "tool_use"),
        message([text_block("Submitted as EXP-0001.")]),
        route_message("finance", 0.9, "follow-up"),
        message([text_block("It is in the queue.")]),
    ])
    orch = Orchestrator(client=client, store=store)
    r1 = orch.handle("claim 30 for lunch, I'm E-1002")
    assert r1.department == "finance" and r1.route.confidence == 0.95 and "EXP-0001" in r1.answer
    r2 = orch.handle("where is it now?")
    assert r2.answer == "It is in the queue."
    # the finance agent kept the earlier turns
    assert len(orch.agent("finance").history) == 6
    assert "hr" not in orch.agents


def test_router_none_gives_a_helpful_answer(store):
    client = FakeClient([route_message("none", 0.2, "sounds like a personal matter")])
    r = Orchestrator(client=client, store=store).handle("what's the meaning of life")
    assert r.department == "none" and "HR, Finance, IT" in r.answer and r.tool_calls == []


def test_refusal_and_max_tokens_are_reported(store):
    client = FakeClient([message([text_block("")], "refusal")])
    r = Orchestrator(client=client, store=store).handle("x", department="it")
    assert r.stop_reason == "refusal" and "can't help" in r.answer
    client = FakeClient([message([text_block("Half an ans")], "max_tokens")])
    r = Orchestrator(client=client, store=store).handle("x", department="it")
    assert r.stop_reason == "max_tokens" and r.answer.endswith("[answer cut short]")


def test_tool_loop_limit(store, monkeypatch):
    from deptagents import config
    monkeypatch.setattr(config, "MAX_TOOL_ROUNDS", 2)
    client = FakeClient([message([tool_use_block("check_system_status", {"system": "ci"})], "tool_use")] * 3)
    r = Orchestrator(client=client, store=store).handle("status", department="it")
    assert r.stop_reason == "tool_limit" and len(r.tool_calls) == 2


def test_unknown_tool_and_unknown_department(store):
    client = FakeClient([message([tool_use_block("launch_rocket", {})], "tool_use"), message([text_block("ok")])])
    r = Orchestrator(client=client, store=store).handle("x", department="hr")
    assert r.tool_calls[0].is_error and "no tool named" in r.tool_calls[0].result
    with pytest.raises(ValueError):
        Orchestrator(client=client, store=store).handle("x", department="legal")
