"""Desktop tidy: "Desktop clean pannu" / "tidy my Downloads".

Sorts the loose files in Desktop or Downloads into kind folders, bins exact duplicates and
installers older than a week, shows the plan, and does it with the normal file tools, so
every step is audited and "Sasu, undo" puts it all back. Only top-level files are touched:
never folders, hidden files, half-finished downloads or anything changed in the last
10 minutes.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FOLDERS = {"desktop": "Desktop", "downloads": "Downloads", "டெஸ்க்டாப்": "Desktop", "டவுன்லோட்ஸ்": "Downloads"}  # fmt: skip
_F = r"(?P<f>desktop|downloads|டெஸ்க்டாப்|டவுன்லோட்ஸ்)"
TRIGGER = re.compile(
    rf"\b(?:tidy|clean|organi[sz]e|sort)\s+(?:up\s+)?(?:my\s+|the\s+)?{_F}"
    rf"|{_F.replace('?P<f>', '?P<g>')}(?:-?(?:a|ai|ah|ஐ|யை))?\s+(?:clean(?:\s*up)?|suthham|sutham|suththam|tidy|organi[sz]e|sort|சுத்தம்)",
    re.IGNORECASE,
)

KINDS: dict[str, set[str]] = {
    "Images": {"png", "jpg", "jpeg", "gif", "heic", "webp", "svg", "tiff", "bmp"},
    "PDFs": {"pdf"},
    "Documents": {
        "doc",
        "docx",
        "pages",
        "txt",
        "rtf",
        "md",
        "odt",
        "xls",
        "xlsx",
        "numbers",
        "csv",
        "ppt",
        "pptx",
        "key",
    },  # fmt: skip
    "Installers": {"dmg", "pkg"},
    "Archives": {"zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz"},
    "Videos": {"mov", "mp4", "m4v", "avi", "mkv", "webm"},
    "Audio": {"mp3", "m4a", "wav", "aac", "flac", "aiff"},
    "Code": {
        "py",
        "js",
        "ts",
        "tsx",
        "json",
        "html",
        "css",
        "swift",
        "java",
        "c",
        "cpp",
        "sh",
        "rb",
        "go",
        "rs",
        "sql",
        "ipynb",
        "yml",
        "yaml",
    },  # fmt: skip
}
SCREENSHOT = re.compile(r"^(?:Screenshot|Screen Shot|CleanShot|Screen Recording)\b", re.IGNORECASE)
PARTIAL = {"crdownload", "download", "part", "partial"}
RECENT_S = 10 * 60
OLD_INSTALLER_S = 7 * 24 * 3600
HASH_LIMIT = 500 * 1024 * 1024  # don't read huge files to look for duplicates


def target(text: str) -> str | None:
    m = TRIGGER.search(text)
    if not m:
        return None
    return FOLDERS[(m.group("f") or m.group("g")).lower()]


@dataclass
class Entry:
    path: Path
    size: int
    mtime: float


@dataclass
class Plan:
    folder: Path
    moves: dict[str, list[Path]] = field(default_factory=dict)
    dupes: list[Path] = field(default_factory=list)
    old_installers: list[Path] = field(default_factory=list)

    @property
    def count(self) -> int:
        return sum(map(len, self.moves.values())) + len(self.dupes) + len(self.old_installers)


def kind_of(name: str) -> str | None:
    if SCREENSHOT.match(name):
        return "Screenshots"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return next((k for k, exts in KINDS.items() if ext in exts), None)


def scan(folder: Path, now: float) -> list[Entry]:
    out: list[Entry] = []
    for p in folder.iterdir():
        if p.name.startswith(".") or p.is_symlink() or not p.is_file():
            continue
        if p.suffix.lstrip(".").lower() in PARTIAL:
            continue
        st = p.stat()
        if now - st.st_mtime < RECENT_S:
            continue  # probably still in use
        out.append(Entry(p, st.st_size, st.st_mtime))
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_plan(entries: list[Entry], folder: Path, now: float) -> Plan:
    plan = Plan(folder)
    by_size: dict[int, list[Entry]] = defaultdict(list)
    for e in entries:
        if 0 < e.size <= HASH_LIMIT:
            by_size[e.size].append(e)
    binned: set[Path] = set()
    for group in by_size.values():
        if len(group) < 2:
            continue
        by_hash: dict[str, list[Entry]] = defaultdict(list)
        for e in group:
            by_hash[sha256(e.path)].append(e)
        for same in by_hash.values():
            keep, *rest = sorted(same, key=lambda e: (e.mtime, len(e.path.name), e.path.name))
            for e in rest:
                plan.dupes.append(e.path)
                binned.add(e.path)
    for e in sorted(entries, key=lambda e: e.path.name.lower()):
        if e.path in binned:
            continue
        kind = kind_of(e.path.name)
        if kind == "Installers" and now - e.mtime > OLD_INSTALLER_S:
            plan.old_installers.append(e.path)
        elif kind is not None:
            plan.moves.setdefault(kind, []).append(e.path)
    plan.moves = dict(sorted(plan.moves.items()))
    return plan


def calls(plan: Plan) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = [
        ("files_move", {"paths": [str(p) for p in paths], "destination": str(plan.folder / kind)})
        for kind, paths in plan.moves.items()
    ]
    if plan.dupes or plan.old_installers:
        out.append(("files_trash", {"paths": [str(p) for p in plan.dupes + plan.old_installers]}))
    return out


TA_KIND = {
    "Screenshots": "screenshot", "Images": "படம்", "PDFs": "PDF", "Documents": "document",
    "Installers": "installer", "Archives": "zip", "Videos": "video", "Audio": "audio", "Code": "code file",
}  # fmt: skip


def steps(plan: Plan, lang: str) -> list[str]:
    out = []
    for kind, paths in plan.moves.items():
        n = len(paths)
        out.append(
            f"{n} {TA_KIND[kind]} → {kind} folder"
            if lang == "ta"
            else f"Move {n} {'file' if n == 1 else 'files'} to {kind}"
        )
    if plan.dupes:
        n = len(plan.dupes)
        out.append(
            f"{n} duplicate-ஐ bin-ல போடு"
            if lang == "ta"
            else f"Bin {n} exact duplicate{'' if n == 1 else 's'}"
        )
    if plan.old_installers:
        n = len(plan.old_installers)
        out.append(
            f"பழைய {n} installer-ஐ bin-ல போடு"
            if lang == "ta"
            else f"Bin {n} installer{'' if n == 1 else 's'} older than a week"
        )
    return out


def summary(plan: Plan, lang: str) -> str:
    where = plan.folder.name
    if lang == "ta":
        return f"{where} சுத்தமாச்சு! {plan.count} file ஒழுங்கா வெச்சுட்டேன். வேண்டாம்னா “undo” சொல்லுங்க."
    return f"{where} is tidy: {plan.count} files sorted. Say “undo” to put it all back."


def plan_for(folder: Path, now: float | None = None) -> Plan:
    now = time.time() if now is None else now
    return make_plan(scan(folder, now), folder, now)
