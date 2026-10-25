"""IT: support tickets, knowledge base, system status."""

from deptagents.departments import SHARED_RULES, Department
from deptagents.store import Store
from deptagents.tools import Tool, ToolError, string

TICKET_CATEGORIES = ["access", "hardware", "software", "network", "security", "other"]
PRIORITIES = ["low", "normal", "high"]


def build(store: Store) -> Department:
    def open_ticket(employee_id: str, category: str, summary: str, priority: str) -> dict:
        """Open a support ticket. Security issues are always high priority."""
        try:
            emp = store.employee(employee_id)
        except KeyError as e:
            raise ToolError(str(e)) from None
        if category == "security":
            priority = "high"
        ticket = {"id": store.next_id("tickets", "IT"), "employee_id": emp["id"], "category": category,
                  "priority": priority, "summary": summary[:200], "status": "open", "created_at": store.now()}
        store.state["tickets"].append(ticket)
        store.save()
        return ticket

    def search_knowledge_base(query: str) -> dict:
        """Search the IT knowledge base for how-to articles."""
        words = [w for w in query.lower().split() if len(w) > 2]
        scored = []
        for article in store.knowledge:
            text = (article["title"] + " " + article["body"]).lower()
            score = sum(text.count(w) for w in words)
            if score:
                scored.append((score, article))
        scored.sort(key=lambda s: -s[0])
        return {"results": [a for _, a in scored[:3]]}

    def check_system_status(system: str) -> dict:
        """Current status of an internal system (email, vpn, wiki, ci, laptops)."""
        s = store.systems.get(system.lower())
        if s is None:
            raise ToolError(f"unknown system {system!r}; known: {', '.join(sorted(store.systems))}")
        return dict(s, system=system.lower())

    tools = [
        Tool("open_ticket", "Open an IT support ticket for an employee.",
             {"employee_id": string("Employee id"), "category": string("Ticket category", TICKET_CATEGORIES),
              "summary": string("One-line summary of the problem"), "priority": string("Priority", PRIORITIES)},
             open_ticket, ["employee_id", "category", "summary", "priority"]),
        Tool("search_knowledge_base", "Search IT how-to articles.", {"query": string("Search words")},
             search_knowledge_base, ["query"]),
        Tool("check_system_status", "Status of an internal system.", {"system": string("System name")},
             check_system_status, ["system"]),
    ]
    return Department(
        key="it", title="IT",
        description="Laptops, accounts and access, software, network, security incidents, system outages.",
        system_prompt="You are the IT support assistant for a small software company. Try the knowledge base "
                      "before opening a ticket for a how-to question. Never ask for passwords; a password reset "
                      "is an access ticket. Anything that smells like a security incident is a high priority ticket.\n"
                      + SHARED_RULES,
        tools=tools,
    )
