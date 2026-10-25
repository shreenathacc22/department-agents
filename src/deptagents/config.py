"""Settings from the environment. No key is ever read here; the SDK resolves credentials itself."""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent.parent

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"      # Claude Opus 5.5 defaults to medium; set it explicitly so it is visible
ROUTER_EFFORT = "low"          # routing is a short classification
MAX_TOKENS = 16000             # non-streaming default from the SDK guidance
ROUTER_MAX_TOKENS = 512
MAX_TOOL_ROUNDS = 12           # stop a runaway loop


def model() -> str:
    return os.environ.get("DEPTAGENTS_MODEL", DEFAULT_MODEL)


def effort() -> str:
    return os.environ.get("DEPTAGENTS_EFFORT", DEFAULT_EFFORT)


def data_dir() -> Path:
    value = os.environ.get("DEPTAGENTS_DATA")
    return Path(value) if value else REPO_DIR / "data"


def state_path() -> Path | None:
    """Where writes (leave requests, expenses, tickets) are kept between runs. Unset means memory only."""
    value = os.environ.get("DEPTAGENTS_STATE")
    return Path(value) if value else None
