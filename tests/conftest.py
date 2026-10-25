import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deptagents.store import Store  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def store(tmp_path):
    return Store(data_dir=DATA, state_path=tmp_path / "state.json")
