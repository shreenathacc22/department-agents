"""The department registry. Each department has a name, a system prompt and tools."""

from dataclasses import dataclass

from deptagents.store import Store
from deptagents.tools import Tool


@dataclass
class Department:
    key: str
    title: str
    description: str   # one line, shown to the router
    system_prompt: str
    tools: list[Tool]


def build_all(store: Store) -> dict[str, Department]:
    from deptagents.departments import finance, hr, it

    depts = [hr.build(store), finance.build(store), it.build(store)]
    return {d.key: d for d in depts}


SHARED_RULES = """
Rules that apply to every department agent:
- You act for one department only. If the request belongs to another department, say which one and stop.
- Use your tools for facts and records. Do not invent balances, amounts, ticket numbers or policy text.
- Confirm what you did in plain words: what you looked up, what you created, and any id you were given.
- Never ask for or repeat passwords, card numbers or other secrets. If someone gives one, tell them not to.
- Keep answers short. Use a list only when there are several items.
- If a tool returns an error, explain it and ask for what is missing instead of guessing.
"""
