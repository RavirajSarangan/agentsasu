"""Parity tests: the Swift core (apps/mac) must behave exactly like the Python core.

Builds the Swift binary once and drives it as the desktop shell would (stdin config,
handshake, WebSocket, control lines). Skipped where Swift isn't installed.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import websockets

from sasu_core.security.audit import AuditLog
from sasu_core.security.redact import redact

PKG = Path(__file__).resolve().parents[2] / "apps" / "mac"
BIN = PKG / ".build" / "release" / "sasu-core-swift"

pytestmark = pytest.mark.skipif(
    shutil.which("swift") is None, reason="Swift toolchain not installed"
)


@pytest.fixture(scope="session")
def swift_bin() -> Path:
    subprocess.run(
        ["swift", "build", "-c", "release", "--package-path", str(PKG)],
        check=True,
        capture_output=True,
    )
    return BIN


class Core:
    def __init__(self, binary: Path, data_dir: Path, dev: bool = False) -> None:
        self.token = secrets.token_urlsafe(32)
        self.data_dir = data_dir
        self.p = subprocess.Popen(
            [str(binary), "--stdin-config"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert self.p.stdin and self.p.stdout
        cfg = {"token": self.token, "data_dir": str(data_dir), "vault_key": "ab" * 32, "dev": dev}
        self.p.stdin.write(json.dumps(cfg) + "\n")
        self.p.stdin.flush()
        self.port = json.loads(self.p.stdout.readline())["port"]

    def control(self, msg: dict[str, Any]) -> None:
        assert self.p.stdin
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def get(self, path: str, auth: bool = False) -> tuple[int, Any]:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if auth:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None

    def stop(self) -> int:
        assert self.p.stdin
        self.p.stdin.close()
        return self.p.wait(5)


@pytest.fixture
def core(swift_bin: Path, tmp_path: Path) -> Iterator[Core]:
    c = Core(swift_bin, tmp_path)
    yield c
    if c.p.poll() is None:
        c.stop()


def ws_url(c: Core, token: str | None = None) -> str:
    return f"ws://127.0.0.1:{c.port}/ws?t={token or c.token}"


async def first_message(url: str, origin: str | None = "tauri://localhost") -> dict[str, Any]:
    headers = {"Origin": origin} if origin else {}
    async with websockets.connect(url, additional_headers=headers, origin=None) as ws:
        return json.loads(await asyncio.wait_for(ws.recv(), 5))


def test_handshake_health_and_auth(core: Core) -> None:
    assert core.get("/api/health") == (200, {"ok": True})
    assert core.get("/api/audit")[0] == 401
    status, rows = core.get("/api/audit", auth=True)
    assert status == 200 and rows[0]["kind"] == "start" and rows[0]["data"]["core"] == "swift"
    assert core.get("/nope")[0] == 404


def test_ws_accepts_app_origin_and_sends_ready(core: Core) -> None:
    msg = asyncio.run(first_message(ws_url(core)))
    assert msg == {"type": "ready", "version": "0.4.0", "demo": False}


@pytest.mark.parametrize(
    ("origin", "token_ok", "reason"),
    [("https://evil.example", True, "origin"), ("tauri://localhost", False, "bad_token")],
)
def test_ws_rejections_are_audited(core: Core, origin: str, token_ok: bool, reason: str) -> None:
    with pytest.raises(websockets.exceptions.InvalidStatus):
        asyncio.run(first_message(ws_url(core, None if token_ok else "x" * 43), origin))
    rows = core.get("/api/audit", auth=True)[1]
    assert rows[0]["kind"] == "rejected" and rows[0]["data"]["reason"] == reason


def test_dev_origin_only_in_dev_mode(swift_bin: Path, tmp_path: Path) -> None:
    prod = Core(swift_bin, tmp_path / "a")
    dev = Core(swift_bin, tmp_path / "b", dev=True)
    try:
        with pytest.raises(websockets.exceptions.InvalidStatus):
            asyncio.run(first_message(ws_url(prod), "http://localhost:1420"))
        assert asyncio.run(first_message(ws_url(dev), "http://localhost:1420"))["type"] == "ready"
    finally:
        prod.stop()
        dev.stop()


def test_rate_limit_size_limit_and_bad_json(core: Core) -> None:
    async def go() -> list[dict[str, Any]]:
        async with websockets.connect(
            ws_url(core), additional_headers={"Origin": "tauri://localhost"}
        ) as ws:
            await ws.recv()
            out = []
            await ws.send("not json")
            out.append(json.loads(await ws.recv()))
            await ws.send("x" * 20_000)
            out.append(json.loads(await ws.recv()))
            for _ in range(30):
                await ws.send(json.dumps({"type": "cancel"}))
                out.append(json.loads(await ws.recv()))
            return out

    msgs = asyncio.run(go())
    assert msgs[0]["code"] == "bad_command"
    assert msgs[1]["code"] == "rate_limited"
    assert msgs[2]["code"] == "not_implemented"
    assert msgs[-1]["code"] == "rate_limited"  # 31st message in 10 s


def test_control_locks_reach_connected_ui(core: Core) -> None:
    async def go() -> list[dict[str, Any]]:
        async with websockets.connect(
            ws_url(core), additional_headers={"Origin": "tauri://localhost"}
        ) as ws:
            await ws.recv()
            core.control({"type": "lock", "reason": "screen"})
            a = json.loads(await asyncio.wait_for(ws.recv(), 5))
            core.control({"type": "unlock", "reason": "screen"})
            b = json.loads(await asyncio.wait_for(ws.recv(), 5))
            return [a, b]

    assert asyncio.run(go()) == [{"type": "locked", "reasons": ["screen"]}, {"type": "unlocked"}]
    core.control(
        {"type": "secret", "provider": "gemini", "key": "AIzaSyEXAMPLEEXAMPLEEXAMPLEEXAMPLE12"}
    )
    core.stop()
    text = (core.data_dir / "audit.sqlite").read_bytes()
    assert b"AIzaSy" not in text  # keys are never logged


def test_audit_chain_is_shared_both_ways(swift_bin: Path, tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    py = AuditLog(db)
    py.append("command", text="நாளைக்கு வருவேன் — ok", n=3, nested={"b": [1, 2.5, None], "a": True})
    py.close()
    c = Core(swift_bin, tmp_path)  # Swift continues the Python chain
    c.control({"type": "lock", "reason": "user"})
    c.control({"type": "unlock", "reason": "user"})
    assert c.stop() == 0
    py = AuditLog(db)
    py.append("after_swift", ok=True)  # Python continues the Swift chain
    status = py.verify()
    py.close()
    assert status.ok and status.entries == 6
    out = subprocess.run(
        [str(swift_bin), "--verify-audit", str(db)], capture_output=True, text=True
    )
    assert json.loads(out.stdout) == {"ok": True, "entries": 6, "broken_at": None}


def test_swift_detects_tampering(swift_bin: Path, tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    py = AuditLog(db)
    for i in range(3):
        py.append("tool", i=i)
    py.close()
    con = sqlite3.connect(db)
    con.execute("DROP TRIGGER audit_no_update")
    con.execute("UPDATE audit SET data = '{\"i\": 99}' WHERE id = 2")
    con.commit()
    con.close()
    out = subprocess.run(
        [str(swift_bin), "--verify-audit", str(db)], capture_output=True, text=True
    )
    assert out.returncode == 1 and json.loads(out.stdout) == {
        "ok": False,
        "entries": 2,
        "broken_at": 2,
    }


@pytest.mark.parametrize(
    "text",
    [
        "my key is sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123",
        "password: hunter2 and token=abc123",
        "card 4242 4242 4242 4242 thanks",
        "AIzaSyD-abcdefghijklmnopqrstuvwxyz012345 in config",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789AB",
        "nothing secret here, just சாசு",
    ],
)
def test_redaction_matches_python(swift_bin: Path, text: str) -> None:
    out = subprocess.run([str(swift_bin), "--redact"], input=text, capture_output=True, text=True)
    assert out.stdout == redact(text)
