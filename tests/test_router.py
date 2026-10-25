import json

from deptagents.departments import build_all
from deptagents.router import route
from fake_client import FakeClient, message, route_message, text_block


def test_route_uses_structured_output_with_department_enum(store):
    client = FakeClient([route_message("it", 0.82, "laptop problem")])
    r = route(client, "my laptop won't turn on", build_all(store))
    assert (r.department, r.confidence, r.reason) == ("it", 0.82, "laptop problem")
    call = client.calls[0]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["format"]["schema"]["properties"]["department"]["enum"] == ["hr", "finance", "it", "none"]
    assert call["output_config"]["effort"] == "low"
    assert call["max_tokens"] <= 1024
    assert "hr:" in call["system"] and "finance:" in call["system"] and "it:" in call["system"]
    assert "thinking" not in call


def test_route_refusal_becomes_none(store):
    client = FakeClient([message([text_block("")], stop_reason="refusal")])
    r = route(client, "anything", build_all(store))
    assert r.department == "none" and r.confidence == 0.0
