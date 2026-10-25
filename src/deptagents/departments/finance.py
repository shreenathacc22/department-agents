"""Finance: budgets, expense claims, expense policy."""

from deptagents.departments import SHARED_RULES, Department
from deptagents.store import Store
from deptagents.tools import Tool, ToolError, number, string

CATEGORIES = ["travel", "meals", "equipment", "software", "training", "other"]


def build(store: Store) -> Department:
    def get_budget(department: str) -> dict:
        """Budget, spend so far and remaining for a department this quarter."""
        b = store.budgets.get(department.lower())
        if b is None:
            raise ToolError(f"no budget line for {department!r}; known: {', '.join(sorted(store.budgets))}")
        spent = b["spent"] + sum(e["amount"] for e in store.state["expenses"] if e["department"] == department.lower() and e["status"] != "rejected")
        return {"department": department.lower(), "quarter": b["quarter"], "budget": b["budget"],
                "spent": round(spent, 2), "remaining": round(b["budget"] - spent, 2)}

    def submit_expense(employee_id: str, amount: float, category: str, description: str) -> dict:
        """Submit an expense claim. Claims over the category limit need finance lead approval."""
        try:
            emp = store.employee(employee_id)
        except KeyError as e:
            raise ToolError(str(e)) from None
        if amount <= 0:
            raise ToolError("amount must be above zero")
        limit = store.policies["finance"]["limits"].get(category)
        needs_approval = limit is not None and amount > limit
        claim = {"id": store.next_id("expenses", "EXP"), "employee_id": emp["id"], "department": emp["department"],
                 "amount": round(amount, 2), "category": category, "description": description,
                 "status": "needs_approval" if needs_approval else "submitted", "created_at": store.now()}
        store.state["expenses"].append(claim)
        store.save()
        return claim

    def expense_policy(category: str) -> dict:
        """The expense rules and limit for a category."""
        fin = store.policies["finance"]
        if category not in fin["limits"]:
            return {"found": False, "categories": sorted(fin["limits"])}
        return {"found": True, "category": category, "limit": fin["limits"][category],
                "rule": fin["rules"].get(category, fin["rules"]["default"])}

    tools = [
        Tool("get_budget", "Quarter budget, spend and remaining for a department (engineering, sales, marketing, operations).",
             {"department": string("Department name")}, get_budget, ["department"]),
        Tool("submit_expense", "Submit an expense claim for an employee.",
             {"employee_id": string("Employee id"), "amount": number("Amount in company currency units"),
              "category": string("Expense category", CATEGORIES), "description": string("What it was for, one line")},
             submit_expense, ["employee_id", "amount", "category", "description"]),
        Tool("expense_policy", "Rules and limit for an expense category.",
             {"category": string("Category", CATEGORIES)}, expense_policy, ["category"]),
    ]
    return Department(
        key="finance", title="Finance",
        description="Budgets, expense claims and reimbursement, spending limits and policy.",
        system_prompt="You are the finance assistant for a small software company. Amounts are in company "
                      "currency units. Claims over a limit need the finance lead; say so when it applies.\n"
                      + SHARED_RULES,
        tools=tools,
    )
