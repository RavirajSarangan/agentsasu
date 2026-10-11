from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from ..security.policy import Decision, path_decision, strictest
from ..undo import inverse
from .registry import ToolContext, ToolResult, obj, tool

PATH = {"type": "string", "description": "Path; ~ means the home folder"}
PATHS = {"type": "array", "items": PATH}
MAX_READ = 20_000


def _p(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _read(args: dict[str, Any]) -> Decision:
    return path_decision(args.get("path") or args.get("folder") or "~", write=False)


def _write_all(*keys: str) -> Any:
    def decide(args: dict[str, Any]) -> Decision:
        paths: list[str] = []
        for k in keys:
            v = args.get(k)
            paths += v if isinstance(v, list) else [v] if v else []
        return (
            strictest("confirm", *(path_decision(p, write=True) for p in paths))
            if paths
            else "deny"
        )

    return decide


def _free_name(target: Path) -> Path:
    if not target.exists():
        return target
    for i in range(1, 1000):
        cand = target.with_name(f"{target.stem} ({i}){target.suffix}")
        if not cand.exists():
            return cand
    raise FileExistsError(target)


@tool(
    "files_find",
    "Find files on this Mac by name (and optionally kind, e.g. pdf, image, presentation).",
    obj(["query"], query={"type": "string"}, kind={"type": "string"}, folder=PATH),
    decide=_read,
    untrusted_output=True,
)
async def files_find(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    folder = str(_p(args.get("folder") or "~"))
    query = str(args["query"]).strip()
    kind = str(args.get("kind") or "").strip()
    if kind:
        p = await ctx.run(["mdfind", "-onlyin", folder, f"kind:{kind}"])
        hits = [
            h
            for h in p.out.splitlines()
            if not query or query == "*" or query.lower() in Path(h).name.lower()
        ]
    else:
        p = await ctx.run(["mdfind", "-onlyin", folder, "-name", query])
        hits = p.out.splitlines()
    hits = [h for h in hits if path_decision(h, write=False) != "deny"][:40]
    return ToolResult(True, f"{len(hits)} found", "\n".join(hits))


@tool(
    "files_list",
    "List what's inside a folder.",
    obj(["folder"], folder=PATH),
    decide=_read,
    untrusted_output=True,
)
async def files_list(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    folder = _p(args["folder"])
    if not folder.is_dir():
        return ToolResult(False, "Not a folder")
    items = sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:80]
    lines = [
        f"{'📁' if i.is_dir() else '📄'} {i.name}" for i in items if not i.name.startswith(".")
    ]
    return ToolResult(True, f"{len(lines)} items", "\n".join(lines))


@tool(
    "files_read",
    "Read a small text file.",
    obj(["path"], path=PATH),
    decide=_read,
    untrusted_output=True,
)
async def files_read(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    path = _p(args["path"])
    if not path.is_file():
        return ToolResult(False, "No such file")
    data = path.read_bytes()[:MAX_READ]
    if b"\x00" in data:
        return ToolResult(False, "That's not a text file")
    return ToolResult(True, f"Read {path.name}", data.decode(errors="replace"))


@tool(
    "files_move",
    "Move files into a folder (created if missing). Undoable.",
    obj(["paths", "destination"], paths=PATHS, destination=PATH),
    risk="confirm",
    decide=_write_all("paths", "destination"),
)
async def files_move(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    dest = _p(args["destination"])
    if not dest.exists():
        dest.mkdir(parents=True)
        ctx.journal.record(ctx.turn_id, "mkdir", path=str(dest))
    moved = 0
    for raw in args["paths"]:
        src = _p(raw)
        if not src.exists():
            continue
        target = _free_name(dest / src.name)
        shutil.move(str(src), str(target))
        ctx.journal.record(ctx.turn_id, "move", src=str(src), dst=str(target))
        moved += 1
    return ToolResult(moved > 0, f"Moved {moved} item(s) to {dest.name}")


@inverse("move", lambda d: f"moved {Path(d['src']).name}")
async def _undo_move(d: dict[str, Any], ctx: ToolContext) -> None:
    shutil.move(d["dst"], str(_free_name(Path(d["src"]))))


@inverse("mkdir", lambda d: f"created folder {Path(d['path']).name}")
async def _undo_mkdir(d: dict[str, Any], ctx: ToolContext) -> None:
    path = Path(d["path"])
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()


@tool(
    "files_rename",
    "Rename a file or folder. Undoable.",
    obj(["path", "new_name"], path=PATH, new_name={"type": "string"}),
    risk="confirm",
    decide=_write_all("path"),
)
async def files_rename(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    src = _p(args["path"])
    name = str(args["new_name"]).strip()
    if not src.exists() or not name or "/" in name or name in {".", ".."}:
        return ToolResult(False, "Can't rename that")
    target = _free_name(src.with_name(name))
    src.rename(target)
    ctx.journal.record(ctx.turn_id, "move", src=str(src), dst=str(target))
    return ToolResult(True, f"Renamed to {target.name}")


@tool(
    "files_new_folder",
    "Create a folder. Undoable.",
    obj(["path"], path=PATH),
    risk="confirm",
    decide=_write_all("path"),
)
async def files_new_folder(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    path = _p(args["path"])
    if path.exists():
        return ToolResult(True, f"{path.name} already exists")
    path.mkdir(parents=True)
    ctx.journal.record(ctx.turn_id, "mkdir", path=str(path))
    return ToolResult(True, f"Created {path.name}")


@tool(
    "files_trash",
    "Throw files away. They go to Sasu's bin, so 'Sasu undo' brings them back.",
    obj(["paths"], paths=PATHS),
    risk="confirm",
    decide=_write_all("paths"),
)
async def files_trash(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    bin_dir = ctx.holding / ctx.turn_id
    bin_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for raw in args["paths"]:
        src = _p(raw)
        if not src.exists():
            continue
        held = bin_dir / f"{uuid.uuid4().hex[:8]}-{src.name}"
        shutil.move(str(src), str(held))
        ctx.journal.record(ctx.turn_id, "trash", src=str(src), held=str(held))
        n += 1
    return ToolResult(n > 0, f"Threw away {n} item(s) — undoable")


@inverse("trash", lambda d: f"threw away {Path(d['src']).name}")
async def _undo_trash(d: dict[str, Any], ctx: ToolContext) -> None:
    shutil.move(d["held"], str(_free_name(Path(d["src"]))))
