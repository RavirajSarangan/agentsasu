import json
import tarfile
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core.security.voiceprint import Voiceprint
from sasu_core.voice.models import MODELS, _keep
from sasu_core.voice.pipeline import Heard
from sasu_core.voice.wake import find_wake, is_stop
from tests.conftest import TOKEN

OWNER = [[1.0, 0.1, 0.0, 0.2], [0.9, 0.15, 0.05, 0.25], [1.1, 0.05, 0.0, 0.18]]


@pytest.mark.parametrize(
    ("text", "heard", "rest"),
    [
        ("Hey Sasu", True, ""),
        ("hey saasu open safari", True, "open safari"),
        ("Hi, Sashu.", True, ""),
        ("hey sa su", True, ""),
        # real tiny/turbo Whisper outputs for synthesized "Hey Sasu…"
        ("Hesasul", True, ""),
        (
            "He Sasuo, opens a fiery and set the volume to 30.",
            True,
            "opens a fiery and set the volume to 30",
        ),
        ("Heis azul.", True, ""),
        ("Hey Sasuar, open Safari", True, "open safari"),
        ("Hey Shasu, Open Terminal.", True, "open terminal"),  # Tamil-accented, as Whisper hears it
        ("she said so", False, ""),
        ("shazam it", False, ""),
        ("சாசு பாட்டு போடு", True, "பாட்டு போடு"),
        ("சாசி ஒரு பாட", True, "ஒரு பாட"),
        ("I said so", False, ""),
        ("sausage rolls for the season", False, ""),
        ("Hey Siri", False, ""),
        ("What is the weather like today?", False, ""),
        ("Downloads lair iroo kira pdf alum list panu.", False, ""),
        # "சாசு" said alone, as Whisper heard it
        ("Sauce", True, ""),
        ("சாச", True, ""),
        ("சாசனம் படி", False, ""),
    ],
)
def test_wake_word(text: str, heard: bool, rest: str) -> None:
    assert find_wake(text) == (heard, rest)


def test_stop_words() -> None:
    assert is_stop("Stop!")
    assert is_stop("நிறுத்து")
    assert not is_stop("don't stop the music playing in the kitchen please")


def test_archives_keep_only_int8_files() -> None:
    wanted = MODELS["stt"].files
    assert _keep(tarfile.TarInfo("sherpa-onnx-whisper-turbo/turbo-encoder.int8.onnx"), wanted)
    assert not _keep(tarfile.TarInfo("sherpa-onnx-whisper-turbo/turbo-encoder.onnx"), wanted)
    assert not _keep(tarfile.TarInfo("../../etc/passwd"), wanted)


def events_until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


def test_voice_status_on_connect(bare_client: TestClient) -> None:
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        status = events_until(ws, "voice_status")[-1]
    assert status["state"] in {"missing", "loading", "listening"}
    assert status["size_mb"] > 600


def test_push_to_talk_without_voice_explains(bare_client: TestClient) -> None:
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        events_until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "ptt_start"}))
        assert "Settings → Voice" in events_until(ws, "error")[-1]["message"]


@pytest.mark.parametrize("mode", ["guest", "reject"])
def test_stranger_voice(bare_client: TestClient, mode: str) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.vault.save(Voiceprint.enroll(OWNER))
    core.settings.guest_mode = mode
    stranger = Heard("delete my files", "en", [0.0, 1.0, 0.8, -0.3], 2.0)
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        events_until(ws, "voice_status")
        bare_client.portal.call(core.voice_command, stranger)  # type: ignore[union-attr]
        events = events_until(ws, "turn_done")
    kinds = [e["type"] for e in events]
    audit = [
        e["kind"]
        for e in bare_client.get("/api/audit", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    ]
    if mode == "reject":
        assert "speaker_rejected" in kinds and "speaker_rejected" in audit
    else:
        assert "guest" in audit and "speaker_rejected" not in kinds


def test_owner_voice_goes_through(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.vault.save(Voiceprint.enroll(OWNER))
    owner = Heard("write a poem about the sea", "en", [1.0, 0.12, 0.02, 0.21], 2.0)
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        events_until(ws, "voice_status")
        bare_client.portal.call(core.voice_command, owner)  # type: ignore[union-attr]
        events = events_until(ws, "turn_done")
    assert not any(e["type"] == "speaker_rejected" for e in events)
    assert (
        next(e for e in events if e["type"] == "error")["code"] == "no_brain"
    )  # owner, just no key yet
