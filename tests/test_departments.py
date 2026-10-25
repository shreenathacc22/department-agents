import json

import pytest

from deptagents.departments import build_all
from deptagents.tools import ToolError


def tool(store, dept, name):
    d = build_all(store)[dept]
    return next(t for t in d.tools if t.name == name)


def test_registry_has_three_departments(store):
    depts = build_all(store)
    assert list(depts) == ["hr", "finance", "it"]
    for d in depts.values():
        assert d.description and d.system_prompt and len(d.tools) == 3
        for t in d.tools:
            api = t.to_api()
            assert api["strict"] is True
            assert api["input_schema"]["additionalProperties"] is False
            assert set(api["input_schema"]["required"]) == set(api["input_schema"]["properties"])


def test_employees_are_ids_and_roles_only(store):
    for emp_id, emp in store.employees.items():
        assert emp_id.startswith("E-")
        assert set(emp) == {"role", "department", "leave"}


# HR ---------------------------------------------------------------------------

def test_hr_leave_balance(store):
    out = json.loads(tool(store, "hr", "get_leave_balance").run({"employee_id": "e-1001"}))
    assert out["employee_id"] == "E-1001" and out["balances_days"]["annual"] == 14
    assert "name" not in out


def test_hr_leave_balance_unknown_employee(store):
    with pytest.raises(ToolError):
        tool(store, "hr", "get_leave_balance").run({"employee_id": "E-9999"})


def test_hr_request_leave_pending_and_persisted(store):
    out = json.loads(tool(store, "hr", "request_leave").run(
        {"employee_id": "E-1001", "start_date": "2026-11-02", "end_date": "2026-11-04", "kind": "annual"}))
    assert out["id"] == "LR-0001" and out["days"] == 3 and out["status"] == "pending"
    assert json.loads(store.state_path.read_text())["leave_requests"][0]["id"] == "LR-0001"
    bal = json.loads(tool(store, "hr", "get_leave_balance").run({"employee_id": "E-1001"}))
    assert bal["pending_requests"][0]["id"] == "LR-0001"


@pytest.mark.parametrize("args, needle", [
    ({"employee_id": "E-1004", "start_date": "2026-11-02", "end_date": "2026-11-06", "kind": "annual"}, "only 2 annual"),
    ({"employee_id": "E-1001", "start_date": "2026-11-06", "end_date": "2026-11-02", "kind": "annual"}, "before"),
    ({"employee_id": "E-1001", "start_date": "next monday", "end_date": "2026-11-02", "kind": "annual"}, "not a date"),
])
def test_hr_request_leave_refusals(store, args, needle):
    with pytest.raises(ToolError) as exc:
        tool(store, "hr", "request_leave").run(args)
    assert needle in str(exc.value)


def test_hr_policy_lookup(store):
    out = json.loads(tool(store, "hr", "lookup_hr_policy").run({"topic": "remote"}))
    assert out["found"] and "three days" in out["policies"]["remote"]
    out = json.loads(tool(store, "hr", "lookup_hr_policy").run({"topic": "parking"}))
    assert not out["found"] and "leave" in out["topics"]


# Finance ----------------------------------------------------------------------

def test_finance_budget_includes_new_claims(store):
    get, submit = tool(store, "finance", "get_budget"), tool(store, "finance", "submit_expense")
    before = json.loads(get.run({"department": "Engineering"}))
    assert before["remaining"] == 16749.5
    claim = json.loads(submit.run({"employee_id": "E-1001", "amount": 49.5, "category": "meals", "description": "customer lunch"}))
    assert claim["id"] == "EXP-0001" and claim["status"] == "submitted"
    after = json.loads(get.run({"department": "engineering"}))
    assert after["remaining"] == 16700.0


def test_finance_over_limit_needs_approval(store):
    claim = json.loads(tool(store, "finance", "submit_expense").run(
        {"employee_id": "E-1002", "amount": 1200, "category": "travel", "description": "conference flights"}))
    assert claim["status"] == "needs_approval"


def test_finance_refusals(store):
    with pytest.raises(ToolError):
        tool(store, "finance", "submit_expense").run({"employee_id": "E-1002", "amount": 0, "category": "meals", "description": "x"})
    with pytest.raises(ToolError):
        tool(store, "finance", "get_budget").run({"department": "legal"})


def test_finance_policy(store):
    out = json.loads(tool(store, "finance", "expense_policy").run({"category": "equipment"}))
    assert out["limit"] == 500 and "IT" in out["rule"]


# IT ---------------------------------------------------------------------------

def test_it_ticket_security_is_high(store):
    t = json.loads(tool(store, "it", "open_ticket").run(
        {"employee_id": "E-1003", "category": "security", "summary": "clicked a phishing link", "priority": "low"}))
    assert t["id"] == "IT-0001" and t["priority"] == "high" and t["status"] == "open"


def test_it_knowledge_base_search(store):
    out = json.loads(tool(store, "it", "search_knowledge_base").run({"query": "forgot my password"}))
    assert out["results"][0]["id"] == "KB-1"
    assert json.loads(tool(store, "it", "search_knowledge_base").run({"query": "zzz"}))["results"] == []


def test_it_system_status(store):
    out = json.loads(tool(store, "it", "check_system_status").run({"system": "VPN"}))
    assert out["status"] == "degraded"
    with pytest.raises(ToolError):
        tool(store, "it", "check_system_status").run({"system": "mainframe"})
