"""Synthetic company data plus the records the agents create.

Reads the JSON files in data/ once. Writes (leave requests, expenses, tickets) stay in memory,
or go to DEPTAGENTS_STATE as JSON when that is set. Employees are ids and roles, never names.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from deptagents import config


class Store:
    def __init__(self, data_dir: Path | None = None, state_path: Path | None = None):
        self.data_dir = data_dir or config.data_dir()
        self.state_path = state_path
        self.employees = self._load("employees.json")
        self.policies = self._load("policies.json")
        self.budgets = self._load("budgets.json")
        self.knowledge = self._load("knowledge_base.json")
        self.systems = self._load("systems.json")
        self.state = {"leave_requests": [], "expenses": [], "tickets": []}
        if self.state_path and self.state_path.exists():
            self.state.update(json.loads(self.state_path.read_text()))

    def _load(self, name: str):
        return json.loads((self.data_dir / name).read_text())

    def save(self) -> None:
        if self.state_path:
            self.state_path.write_text(json.dumps(self.state, indent=1))

    # helpers ---------------------------------------------------------------

    def employee(self, employee_id: str) -> dict:
        emp = self.employees.get(employee_id.upper())
        if emp is None:
            raise KeyError(f"no employee with id {employee_id}")
        return dict(emp, id=employee_id.upper())

    def next_id(self, kind: str, prefix: str) -> str:
        return f"{prefix}-{len(self.state[kind]) + 1:04d}"

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def parse_date(value: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{value!r} is not a date in YYYY-MM-DD form") from None
