"""Strip secrets before anything is logged or sent to an LLM."""

from __future__ import annotations

import re
from typing import Any

MASK = "«redacted»"

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),  # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),  # OpenAI-style
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),  # GitHub tokens
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"),  # Slack
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),  # Google API key
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),  # card-like numbers
    re.compile(
        r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
    ),
]


def redact(text: str) -> str:
    for pat in _PATTERNS[:-1]:
        text = pat.sub(MASK, text)
    return _PATTERNS[-1].sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)


def redact_obj(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_obj(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact_obj(v) for v in value]
    return value
