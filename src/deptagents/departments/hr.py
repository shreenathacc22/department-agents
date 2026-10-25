"""HR: leave balances, leave requests, HR policy lookups."""

from deptagents.departments import SHARED_RULES, Department
from deptagents.store import Store
from deptagents.tools import Tool, ToolError, string

LEAVE_KINDS = ["annual", "sick", "parental", "unpaid"]


def build(store: Store) -> Department:
    def get_leave_balance(employee_id: str) -> dict:
        """Leave balances for one employee by id."""
        try:
            emp = store.employee(employee_id)
        except KeyError as e:
            raise ToolError(str(e)) from None
        pending = [r for r in store.state["leave_requests"] if r["employee_id"] == emp["id"] and r["status"] == "pending"]
        return {"employee_id": emp["id"], "role": emp["role"], "department": emp["department"],
                "balances_days": emp["leave"], "pending_requests": pending}

    def request_leave(employee_id: str, start_date: str, end_date: str, kind: str) -> dict:
        """Record a leave request. It is pending until a manager approves it."""
        try:
            emp = store.employee(employee_id)
            start, end = store.parse_date(start_date), store.parse_date(end_date)
        except (KeyError, ValueError) as e:
            raise ToolError(str(e)) from None
        if end < start:
            raise ToolError("end_date is before start_date")
        days = (end - start).days + 1
        if kind != "unpaid" and days > emp["leave"].get(kind, 0):
            raise ToolError(f"only {emp['leave'].get(kind, 0)} {kind} days left, {days} requested")
        req = {"id": store.next_id("leave_requests", "LR"), "employee_id": emp["id"], "kind": kind,
               "start_date": start.isoformat(), "end_date": end.isoformat(), "days": days,
               "status": "pending", "created_at": store.now()}
        store.state["leave_requests"].append(req)
        store.save()
        return req

    def lookup_hr_policy(topic: str) -> dict:
        """Find the HR policy on a topic (leave, remote work, expenses handled by finance, conduct, onboarding)."""
        hits = {k: v for k, v in store.policies["hr"].items() if topic.lower() in k or topic.lower() in v.lower()}
        if not hits:
            return {"found": False, "topics": sorted(store.policies["hr"])}
        return {"found": True, "policies": hits}

    tools = [
        Tool("get_leave_balance", "Leave balances and pending leave requests for an employee id like E-1001.",
             {"employee_id": string("Employee id, e.g. E-1001")}, get_leave_balance, ["employee_id"]),
        Tool("request_leave", "Create a pending leave request for an employee. Dates are YYYY-MM-DD, inclusive.",
             {"employee_id": string("Employee id"), "start_date": string("First day, YYYY-MM-DD"),
              "end_date": string("Last day, YYYY-MM-DD"), "kind": string("Kind of leave", LEAVE_KINDS)},
             request_leave, ["employee_id", "start_date", "end_date", "kind"]),
        Tool("lookup_hr_policy", "Look up the company HR policy on a topic.",
             {"topic": string("Topic word, e.g. remote, leave, onboarding")}, lookup_hr_policy, ["topic"]),
    ]
    return Department(
        key="hr", title="HR",
        description="Leave balances and requests, HR policies, onboarding, conduct questions.",
        system_prompt="You are the HR assistant for a small software company. Employees are identified by id, "
                      "never by name. Leave requests you create are pending until a manager approves them; say so.\n"
                      + SHARED_RULES,
        tools=tools,
    )
