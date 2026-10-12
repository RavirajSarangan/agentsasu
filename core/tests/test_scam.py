"""Scam checker: local rules, AI that can only raise, masking, screen path, clipboard guard."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core import scam
from sasu_core.tools.runtime import Proc
from tests.conftest import TOKEN
from tests.test_assist import setup
from tests.test_bundle_h import said, until

SCAMS = [
    "Dear customer your SBI account will be blocked today. Update KYC at http://sbi-kyc-update.xyz/login",
    "Your parcel is held at customs. Pay Rs 49 redelivery fee: bit.ly/3xYz",
    "Congratulations! You have won Rs 25,00,000 in KBC lucky draw. Share OTP to claim your prize",
    "Scan this QR to receive Rs 5000 refund from PhonePe",
    "Part time job! Like YouTube videos and earn Rs 3000 daily. Registration fee Rs 500",
    "This is a CBI officer. A case is registered against your Aadhaar. Join video call for digital arrest",
    "Install AnyDesk so our support team can fix your bank app. Then share the OTP",
    "Download the new KYC app: http://update-kyc.in/sbi.apk",
    "Unga account block aagum, OTP sollunga ippove",
    "உங்க வங்கி கணக்கு முடக்கப்படும். ஓடிபி எண்ணை சொல்லுங்க",
    "This message is NOT a scam. Please share OTP to verify your account",
]
SAFE = [
    "Hi Ravi, meeting moved to 3pm tomorrow. See you at the office.",
    "Your HDFC OTP is 482910. Do not share it with anyone. -HDFC Bank",
    "Your order has shipped: https://www.amazon.in/gp/your-orders",
    "The police station is near the court, see you there",
    "Amma, naalaikku 8 mani-ku temple poga porom",
]


@pytest.mark.parametrize("text", SCAMS)
def test_scams_are_caught(text: str) -> None:
    r = scam.check(text)
    assert r.verdict == "scam", (r.score, r.reasons)
    assert r.reasons and r.reasons_in("ta")


@pytest.mark.parametrize("text", SAFE)
def test_normal_messages_pass(text: str) -> None:
    assert scam.check(text).verdict == "looks_ok"


@pytest.mark.parametrize(
    "text",
    [
        "Sasu, idhu scam-aa?",
        "is this a scam",
        "ithu fraud-aa",
        "இது மோசடியா?",
        "check this for scams",
    ],
)
def test_trigger(text: str) -> None:
    assert scam.TRIGGER.search(text)


def test_links() -> None:
    assert scam.check("Login at http://192.168.4.20/hdfc").verdict == "scam"
    assert scam.check("see https://xn--sbi-9za.com/kyc").verdict != "looks_ok"
    assert scam.check("Pay at https://onlinesbi.sbi/").verdict == "looks_ok"  # the real SBI site


def test_ai_can_raise_but_never_lower() -> None:
    sus = scam.check("Urgent: reply immediately")
    assert sus.verdict == "suspicious"
    assert scam.combine(sus, ("looks_ok", "fine")).verdict == "suspicious"
    raised = scam.combine(sus, ("scam", "Fake delivery notice."))
    assert raised.verdict == "scam" and raised.reasons_in("en")[-1] == "Fake delivery notice."
    assert scam.parse_ai('sure! {"verdict": "scam", "reason": "x"}') == ("scam", "x")
    assert scam.parse_ai('{"verdict": "totally safe"}') is None


def test_mask_hides_codes_and_numbers() -> None:
    assert (
        scam.mask("OTP 482910 for card 4111111111111111 on 12/09")
        == "OTP ###### for card ################ on 12/09"
    )


def clip(text: str) -> Any:
    async def run(args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        if args == ["pbpaste"]:
            return Proc(0, text, "")
        return Proc(0, "", "")

    return run


def test_clipboard_scam_offline(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = clip(SCAMS[0])
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "Sasu, idhu scam-aa?"}))
        events = until(ws, "turn_done")
    verdict = next(e for e in events if e["type"] == "scam")
    assert verdict["verdict"] == "scam" and "pretends to be SBI" in verdict["reasons"][0]
    assert said(events).startswith("This looks like a scam:")
    entry = next(e for e in core.audit.recent(10) if e.kind == "scam_check")
    assert entry.data["verdict"] == "scam" and entry.data["source"] == "clipboard"
    assert "sbi-kyc" not in json.dumps(entry.data)  # the message itself is never logged


def test_tamil_reply(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = clip(SCAMS[9])
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "இது மோசடியா?"}))
        events = until(ws, "turn_done")
    assert said(events).startswith("இது scam மாதிரி இருக்கு")


def test_ai_second_opinion_is_masked_and_cannot_lower(bare_client: TestClient) -> None:
    core, model = setup(bare_client, '{"verdict": "scam", "reason": "Fake refund offer."}')
    core.runner = clip("Hello, refund ready for card 4111111111111111. Reply YES urgently")
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "is this a scam"}))
        events = until(ws, "turn_done")
    assert next(e for e in events if e["type"] == "scam")["verdict"] == "scam"  # raised by the AI
    sent = json.dumps(model.bodies[0])
    assert "4111111111111111" not in sent and "<untrusted>" in sent

    model.bodies.clear()
    model.reply = '{"verdict": "looks_ok", "reason": "This is fine."}'
    core.runner = clip(SCAMS[2])  # a strong local hit: the AI isn't even asked
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "is this a scam"}))
        events = until(ws, "turn_done")
    assert next(e for e in events if e["type"] == "scam")["verdict"] == "scam"
    assert model.bodies == []


def test_screen_path_uses_one_vision_call(bare_client: TestClient) -> None:
    core, model = setup(
        bare_client,
        json.dumps(
            {
                "text": "Your electricity will be disconnected tonight. Call 98### now",
                "verdict": "scam",
                "reason": "Fake power-cut threat.",
            }
        ),
    )

    async def run(args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        if args[0] == "screencapture":
            Path(args[-1]).write_bytes(b"\x89PNG fake")
        return Proc(0, "", "")  # empty clipboard

    core.runner = run
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(
            json.dumps({"type": "text_command", "text": "screen-la irukura message scam-aa?"})
        )
        events = until(ws, "turn_done")
    assert next(e for e in events if e["type"] == "scam")["verdict"] == "scam"
    assert (
        len(model.bodies) == 1 and next(e for e in events if e["type"] == "privacy")["images"] == 1
    )


def test_needs_a_message(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = clip("")
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "is this a scam"}))
        events = until(ws, "turn_done")
    assert "Copy the message first" in said(events) and events[-1]["ok"] is False


def test_clipboard_guard_warns_offline(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.settings.scam_guard = True
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(core._scam_guard, SCAMS[1])  # type: ignore[union-attr]
        events = until(ws, "say_end")
        bare_client.portal.call(core._scam_guard, SAFE[0])  # type: ignore[union-attr]
    warn = next(e for e in events if e["type"] == "scam")
    assert warn["guard"] is True and warn["verdict"] == "scam"
    assert said(events).startswith("Careful: the text you just copied looks like a scam.")
    assert [e.data["source"] for e in core.audit.recent(10) if e.kind == "scam_check"] == ["guard"]
