from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sasu_core.server import create_app

TOKEN = "t" * 43


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Core with scripted demo turns (no background loop) and a silent voice."""
    app = create_app(TOKEN, data_dir=tmp_path, delay=0.01)
    core = app.state.core
    core.demo = True
    core.speaker.enabled = False
    core.settings.tts = False
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bare_client(tmp_path: Path) -> Iterator[TestClient]:
    """Core with no demo and no AI key."""
    app = create_app(TOKEN, data_dir=tmp_path, delay=0.01)
    app.state.core.speaker.enabled = False
    app.state.core.settings.tts = False
    with TestClient(app) as c:
        yield c
