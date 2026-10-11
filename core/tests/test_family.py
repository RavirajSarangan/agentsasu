import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core.brain.agent import Executor, Turn
from sasu_core.security.roles import allowed
from sasu_core.security.voiceprint import Profile, Voiceprint, VoiceprintVault, identify
from sasu_core.voice.pipeline import Heard
from sasu_core.voice.wake import find_wake
from tests.conftest import TOKEN

KEY = "ab" * 32
OWNER = [[1.0, 0.1, 0.0, 0.2], [0.9, 0.15, 0.05, 0.25], [1.1, 0.05, 0.0, 0.18]]
KID = [[0.0, 1.0, 0.2, 0.0], [0.05, 0.95, 0.25, 0.0], [0.0, 1.05, 0.15, 0.05]]


def test_old_single_voiceprint_migrates_to_owner(tmp_path: Path) -> None:
    vault = VoiceprintVault(tmp_path / "v.bin", KEY)
    # write the v0.3 format directly
    import os

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    body = json.dumps({"centroid": [1.0, 0.0], "threshold": 0.7}).encode()
    (tmp_path / "v.bin").write_bytes(
        nonce + AESGCM(bytes.fromhex(KEY)).encrypt(nonce, body, VoiceprintVault.AAD)
    )
    [p] = vault.load_profiles()
    assert (p.name, p.role) == ("Owner", "owner")


def test_identify_picks_the_right_person(tmp_path: Path) -> None:
    vault = VoiceprintVault(tmp_path / "v.bin", KEY)
    vault.upsert(Profile("Raviraj", "owner", Voiceprint.enroll(OWNER)))
    profiles = vault.upsert(Profile("Kutty", "kid", Voiceprint.enroll(KID)))
    who, _ = identify(profiles, [0.02, 1.0, 0.2, 0.0])
    assert who is not None and who.name == "Kutty" and who.role == "kid"
    nobody, score = identify(profiles, [0.0, 0.0, -1.0, 1.0])
    assert nobody is None and score < 0.68
    assert b"Kutty" not in (tmp_path / "v.bin").read_bytes()  # encrypted


@pytest.mark.parametrize(
    ("role", "tool", "args", "decision", "expected"),
    [
        ("owner", "shell_run", {}, "confirm", "confirm"),
        ("family", "files_trash", {}, "confirm", "confirm"),
        ("family", "files_trash", {}, "dangerous", "deny"),
        ("family", "shell_run", {}, "confirm", "deny"),
        ("kid", "media_control", {}, "safe", "safe"),
        ("kid", "apps_open", {"app": "Terminal"}, "safe", "deny"),
        ("kid", "web_open", {"url": "youtube.com"}, "safe", "safe"),
        ("kid", "web_open", {"url": "https://evil.example"}, "safe", "deny"),
        ("guest", "apps_open", {"app": "Safari"}, "safe", "deny"),
        ("guest", "media_control", {}, "safe", "safe"),
    ],
)
def test_role_rules(
    role: str, tool: str, args: dict[str, Any], decision: str, expected: str
) -> None:
    assert allowed(role, tool, args, decision) == expected  # type: ignore[arg-type]


def test_executor_applies_kid_role(tmp_path: Path) -> None:
    from sasu_core.security.audit import AuditLog
    from sasu_core.undo import Journal

    async def emit(e: Any) -> None: ...

    async def approve(*a: Any) -> bool:
        return True

    ex = Executor(
        emit,
        approve,
        AuditLog(tmp_path / "a.sqlite"),
        Journal(tmp_path / "u.sqlite"),
        tmp_path / "bin",
    )
    assert ex.decision("apps_open", {"app": "Terminal"}, Turn("t", "en", role="kid")) == "deny"
    assert ex.decision("apps_open", {"app": "Terminal"}, Turn("t", "en", role="owner")) == "safe"


@pytest.mark.parametrize(
    ("text", "names", "heard"),
    [
        ("Hey Chitti, open Safari", ("Chitti",), True),
        ("hey chiti open safari", ("Chitti",), True),
        ("சிட்டி பாட்டு போடு", ("சிட்டி",), True),
        ("Hey Sasu", ("Chitti",), True),
        ("pretty city lights", ("Chitti",), False),
        ("I bought a kitten", ("Chitti",), False),
    ],
)
def test_custom_robot_names(text: str, names: tuple[str, ...], heard: bool) -> None:
    assert find_wake(text, names)[0] is heard


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


def test_kid_voice_cannot_open_terminal(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.vault.upsert(Profile("Raviraj", "owner", Voiceprint.enroll(OWNER)))
    core.vault.upsert(Profile("Kutty", "kid", Voiceprint.enroll(KID)))
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(
            core.voice_command, Heard("open Terminal", "en", [0.02, 1.0, 0.2, 0.0], 2.0)
        )  # type: ignore[union-attr]
        events = until(ws, "turn_done")
    said = "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))
    assert "only my owner" in said
    assert not any(c[:2] == ["open", "-a"] for c in core.runner.calls)
