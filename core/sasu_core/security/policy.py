"""Least-privilege rules every tool call is checked against (Phase 3+ tools use these).

Each check returns a risk tier, or "deny" for things Sasu must never do on voice
command. Tiers: safe (run), confirm (owner yes), dangerous (Touch ID / password).
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Literal

Decision = Literal["safe", "confirm", "dangerous", "deny"]
_ORDER: dict[Decision, int] = {"safe": 0, "confirm": 1, "dangerous": 2, "deny": 3}

HOME = Path(os.path.expanduser("~")).resolve()

# Never readable or writable, even with Touch ID.
DENY_PATHS = [
    HOME / ".ssh",
    HOME / ".gnupg",
    HOME / ".aws",
    HOME / "Library" / "Keychains",
    HOME / "Library" / "Cookies",
    HOME / "Library" / "Application Support" / "dev.sasu.desktop",  # our own vault + audit
    Path("/System"),
    Path("/private/etc"),
    Path("/etc"),
    Path("/private/var/db"),
]

SAFE_COMMANDS = {
    "ls",
    "pwd",
    "whoami",
    "date",
    "cal",
    "uptime",
    "df",
    "du",
    "echo",
    "cat",
    "head",
    "tail",
    "wc",
    "file",
    "which",
    "sw_vers",
    "system_profiler",
    "pmset",
    "open",
    "say",
    "mdfind",
    "find",
    "grep",
    "sort",
    "uniq",
    "diskutil",
    "networksetup",
    "ping",
    "git",
}
CONFIRM_COMMANDS = {
    "mv",
    "cp",
    "mkdir",
    "touch",
    "zip",
    "unzip",
    "tar",
    "kill",
    "killall",
    "osascript",
    "brew",
    "npm",
    "pnpm",
    "pip",
    "uv",
    "defaults",
    "curl",
    "wget",
}
DANGEROUS_COMMANDS = {
    "rm",
    "rmdir",
    "chmod",
    "chown",
    "launchctl",
    "shutdown",
    "reboot",
    "dd",
    "diskutil eraseDisk",
    "srm",
    "trash",
}
DENY_COMMANDS = {
    "sudo",
    "su",
    "doas",
    "passwd",
    "security",
    "csrutil",
    "nvram",
    "spctl",
    "mkfs",
    "fdisk",
    "visudo",
    "crontab",
}
SHELLS = {"sh", "bash", "zsh", "fish", "python", "python3", "node", "perl", "ruby"}


def strictest(*decisions: Decision) -> Decision:
    return max(decisions, key=lambda d: _ORDER[d])


def bump(decision: Decision) -> Decision:
    """One tier stricter: used when a call follows untrusted content (prompt injection)."""
    return {"safe": "confirm", "confirm": "dangerous", "dangerous": "dangerous", "deny": "deny"}[
        decision
    ]  # type: ignore[return-value]


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def path_decision(path: str | Path, *, write: bool) -> Decision:
    p = Path(os.path.expanduser(str(path))).resolve()
    if any(_inside(p, d) for d in DENY_PATHS):
        return "deny"
    if not _inside(p, HOME):
        return "dangerous" if write else "confirm"
    return "confirm" if write else "safe"


def shell_decision(command: str) -> Decision:
    """Classify a shell command line. Anything we can't parse safely is dangerous."""
    if any(tok in command for tok in ("`", "$(", "<(", ">(")):
        return "dangerous"
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return "dangerous"
    if not tokens:
        return "deny"

    decision: Decision = "safe"
    segment_start = True
    for i, tok in enumerate(tokens):
        if tok in {";", "&&", "||", "|", "&"}:
            if tok == "|" and i + 1 < len(tokens) and tokens[i + 1] in SHELLS:
                return "deny"  # curl … | sh
            segment_start = True
            continue
        if tok in {">", ">>", "<"}:
            decision = strictest(decision, "confirm")
            continue
        if not segment_start:
            if tok in {"-rf", "-fr", "-r", "-R"} and decision == "dangerous":
                nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
                if nxt in {"/", "~", "/*", "~/", os.path.expanduser("~")}:
                    return "deny"
            continue
        segment_start = False
        name = os.path.basename(tok)
        if name in DENY_COMMANDS:
            return "deny"
        if name in SHELLS or name in DANGEROUS_COMMANDS:
            decision = strictest(decision, "dangerous")
        elif name in CONFIRM_COMMANDS:
            decision = strictest(decision, "confirm")
        elif name not in SAFE_COMMANDS:
            decision = strictest(decision, "dangerous")
    return decision


SENDING_TOOLS = {"mail.send", "messages.send", "web.post", "files.upload", "browser.submit"}


def tool_floor(tool: str) -> Decision:
    """Minimum tier for a tool regardless of its arguments."""
    return "confirm" if tool in SENDING_TOOLS else "safe"
