"""One OpenAI-compatible client for every free (and paid) model provider."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    base_url: str
    default_model: str
    prefer: str  # regex; newest matching model wins
    needs_key: bool = True
    free: bool = True
    privacy_note: str = ""


SPECS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        "gemini",
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.5-flash",
        r"^gemini-(\d+(?:\.\d+)?)-flash$",
        privacy_note="Free tier: Google may use prompts to improve its products.",
    ),
    "groq": ProviderSpec(
        "groq",
        "Groq",
        "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile",
        r"^llama-(\d+(?:\.\d+)?)-70b-versatile$",
    ),
    "anthropic": ProviderSpec(
        "anthropic",
        "Anthropic Claude",
        "https://api.anthropic.com/v1",
        "claude-sonnet-5-5",
        r"^claude-sonnet-(\d+(?:-\d+)?)$",
        free=False,
    ),
    "ollama": ProviderSpec(
        "ollama",
        "Ollama (offline)",
        "http://127.0.0.1:11434/v1",
        "qwen3:8b",
        r"^qwen(\d+(?:\.\d+)?)",
        needs_key=False,
        privacy_note="Runs on this Mac. Nothing leaves it.",
    ),
}


class LLMError(Exception):
    """A problem worth telling the user about in plain words."""


def _version(m: re.Match[str]) -> tuple[float, ...]:
    return tuple(float(x) for x in re.split(r"[.-]", m.group(1)) if x)


def pick_model(spec: ProviderSpec, available: list[str], preferred: str | None = None) -> str:
    """The user's choice if available, else the newest model matching the provider preference."""
    if preferred and preferred in available:
        return preferred
    pattern = re.compile(spec.prefer)
    matches = [(m, name) for name in available if (m := pattern.search(name))]
    if matches:
        return max(matches, key=lambda mn: _version(mn[0]))[1]
    return spec.default_model if spec.default_model in available or not available else available[0]


class ChatClient:
    def __init__(
        self,
        spec: ProviderSpec,
        key: str | None,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.spec = spec
        self.model = model
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._http = httpx.AsyncClient(
            base_url=spec.base_url, headers=headers, timeout=60, transport=transport
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _raise(self, r: httpx.Response) -> None:
        if r.status_code in (401, 403):
            raise LLMError(
                f"{self.spec.label} rejected the API key. Check it in Settings → AI brain."
            )
        if r.status_code == 429:
            raise LLMError(f"{self.spec.label} free limit reached — try again in a minute.")
        if r.status_code >= 400:
            raise LLMError(f"{self.spec.label} error {r.status_code}: {r.text[:200]}")

    async def list_models(self) -> list[str]:
        try:
            r = await self._http.get("/models")
        except httpx.HTTPError:
            return []
        if r.status_code != 200:
            return []
        return [str(m.get("id", "")).removeprefix("models/") for m in r.json().get("data", [])]

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0.3}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        try:
            r = await self._http.post("/chat/completions", json=body)
        except httpx.HTTPError as e:
            raise LLMError(f"Couldn't reach {self.spec.label}: {e.__class__.__name__}") from e
        self._raise(r)
        choices = r.json().get("choices") or []
        if not choices:
            raise LLMError(f"{self.spec.label} returned no answer")
        msg: dict[str, Any] = choices[0]["message"]
        return msg
