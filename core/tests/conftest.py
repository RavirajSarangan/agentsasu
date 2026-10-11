from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sasu_core.server import create_app
from sasu_core.tools.runtime import Proc


class FakeRun:
    """Records commands instead of running them: tests never touch the real Mac."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, args: object, timeout: float = 15, stdin: str | None = None) -> Proc:
        self.calls.append(list(args))  # type: ignore[call-overload]
        return Proc(0, "50", "")


TOKEN = "t" * 43


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Core with scripted demo turns (no background loop) and a silent voice."""
    app = create_app(TOKEN, data_dir=tmp_path, delay=0.01)
    core = app.state.core
    core.demo = True
    core.runner = FakeRun()
    core.speaker.enabled = False
    core.settings.tts = False
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bare_client(tmp_path: Path) -> Iterator[TestClient]:
    """Core with no demo and no AI key."""
    app = create_app(TOKEN, data_dir=tmp_path, delay=0.01)
    app.state.core.runner = FakeRun()
    app.state.core.speaker.enabled = False
    app.state.core.settings.tts = False
    with TestClient(app) as c:
        yield c
