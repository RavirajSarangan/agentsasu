"""FastAPI app: token-guarded WebSocket for events, small REST surface."""

from __future__ import annotations

import asyncio
import contextlib
import re
import secrets
import time
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi import status as http
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from . import __version__, care
from .core import Core
from .demo import demo_loop
from .hub import Hub
from .protocol import ErrorEvent, Locked, Ready, ui_command_adapter
from .security.audit import AuditLog
from .security.voiceprint import VoiceprintVault


class CareIn(BaseModel):
    who: str = Field(min_length=1, max_length=40)
    what: str = Field(min_length=1, max_length=80)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)


APP_ORIGINS = {"tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"}
DEV_ORIGINS = {"http://localhost:1420", "http://127.0.0.1:1420"}

RATE_WINDOW_S = 10.0
RATE_MAX = 30


class RateLimiter:
    def __init__(self, limit: int = RATE_MAX, window: float = RATE_WINDOW_S) -> None:
        self.limit, self.window = limit, window
        self.hits: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self.hits and now - self.hits[0] > self.window:
            self.hits.popleft()
        if len(self.hits) >= self.limit:
            return False
        self.hits.append(now)
        return True


def create_app(
    token: str,
    *,
    data_dir: Path,
    vault_key: str | None = None,
    demo: bool = False,
    delay: float = 1.0,
    dev: bool = False,
) -> FastAPI:
    if len(token) < 32 and not dev:
        raise ValueError("token too short")
    data_dir.mkdir(parents=True, exist_ok=True)
    data_dir.chmod(0o700)
    audit = AuditLog(data_dir / "audit.sqlite")
    vault = VoiceprintVault(data_dir / "voiceprint.bin", vault_key or secrets.token_hex(32))
    hub = Hub()
    core = Core(hub, audit, vault, data_dir, demo=demo, delay=delay)
    origins = APP_ORIGINS | (DEV_ORIGINS if dev else set())

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        audit.append("start", version=__version__, demo=demo, dev=dev)
        task = (
            asyncio.create_task(demo_loop(hub.emit, delay=delay, paused=lambda: core.locked))
            if demo
            else asyncio.create_task(core.boot())  # start listening if voice models are on disk
        )
        yield
        if task:
            task.cancel()
        core.close()
        audit.append("stop")
        audit.close()

    app = FastAPI(
        title="sasu-core",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.state.core = core

    def require_token(authorization: str = Header(default="")) -> None:
        if not secrets.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
            raise HTTPException(http.HTTP_401_UNAUTHORIZED)

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {"ok": True}

    @app.get("/api/security", dependencies=[Depends(require_token)])
    async def security() -> dict[str, Any]:
        chain = audit.verify()
        return {
            "locked": core.locked,
            "lockReasons": sorted(core.locks),
            "voiceprintEnrolled": vault.path.exists(),
            "voice": core.voice_state.state,
            "audit": {"ok": chain.ok, "entries": chain.entries, "brokenAt": chain.broken_at},
            "bind": "127.0.0.1",
            "demo": demo,
        }

    photo_name = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}\.jpg$")

    @app.post("/api/intruders", dependencies=[Depends(require_token)])
    async def upload_photo(
        request: Request, snap: str = Query(..., max_length=32)
    ) -> dict[str, str]:
        body = await request.body()
        name = core.accept_photo(snap, body[:400_001])
        if name is None:
            raise HTTPException(http.HTTP_400_BAD_REQUEST, "not requested, expired or invalid")
        return {"file": name}

    @app.get("/api/intruders", dependencies=[Depends(require_token)])
    async def list_photos() -> list[str]:
        d = core.photos_dir
        return (
            sorted((p.name for p in d.glob("*.jpg") if photo_name.match(p.name)), reverse=True)
            if d.exists()
            else []
        )

    @app.get("/api/intruders/{name}", dependencies=[Depends(require_token)])
    async def get_photo(name: str) -> FileResponse:
        if not photo_name.match(name) or not (core.photos_dir / name).is_file():
            raise HTTPException(http.HTTP_404_NOT_FOUND)
        return FileResponse(core.photos_dir / name, media_type="image/jpeg")

    @app.delete("/api/intruders/{name}", dependencies=[Depends(require_token)])
    async def delete_photo(name: str) -> dict[str, bool]:
        if not photo_name.match(name):
            raise HTTPException(http.HTTP_404_NOT_FOUND)
        (core.photos_dir / name).unlink(missing_ok=True)
        audit.append("intruder_photo", deleted=name)
        return {"ok": True}

    @app.get("/api/memory", dependencies=[Depends(require_token)])
    async def list_memory() -> list[dict[str, Any]]:
        return [{"id": f.id, "text": f.text, "at": f.at} for f in reversed(core.memory.all())]

    @app.delete("/api/memory/{fid}", dependencies=[Depends(require_token)])
    async def delete_memory(fid: str) -> dict[str, int]:
        n = core.memory.forget(fid) if re.fullmatch(r"[0-9a-f]{10}", fid) else 0
        audit.append("memory", action="delete", removed=n)
        return {"removed": n}

    @app.get("/api/care", dependencies=[Depends(require_token)])
    async def list_care() -> list[dict[str, Any]]:
        now = core.clock()
        return [
            {"id": d.id, "who": d.who, "what": d.what, "hour": d.hour, "minute": d.minute,
             "status": core.care.status(d, now)}
            for d in sorted(core.care_store.all(), key=lambda d: (d.hour, d.minute))
        ]  # fmt: skip

    @app.post("/api/care", dependencies=[Depends(require_token)])
    async def add_care(body: CareIn) -> dict[str, str]:
        d = core.care_store.add(
            care.Dose(
                secrets.token_hex(4), body.who.strip(), body.what.strip(), body.hour, body.minute
            )
        )
        audit.append("care", action="add", who=d.who, at=f"{d.hour:02d}:{d.minute:02d}")
        return {"id": d.id}

    @app.delete("/api/care/{did}", dependencies=[Depends(require_token)])
    async def delete_care(did: str) -> dict[str, bool]:
        ok = bool(re.fullmatch(r"[0-9a-f]{8}", did)) and core.care_store.remove(did)
        audit.append("care", action="delete", removed=ok)
        return {"ok": ok}

    @app.get("/api/skills", dependencies=[Depends(require_token)])
    async def skills() -> list[dict[str, Any]]:
        return [{"name": n, "steps": len(core.skills.get(n) or [])} for n in core.skills.names()]

    @app.get("/api/audit", dependencies=[Depends(require_token)])
    async def audit_log(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, Any]]:
        return [
            {"id": e.id, "at": e.at, "kind": e.kind, "data": e.data, "hash": e.hash}
            for e in audit.recent(limit)
        ]

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket, t: str = Query(default="")) -> None:
        origin = ws.headers.get("origin")
        if origin is not None and origin not in origins:
            audit.append("rejected", reason="origin", origin=origin)
            await ws.close(code=http.WS_1008_POLICY_VIOLATION)
            return
        if not secrets.compare_digest(t.encode(), token.encode()):
            audit.append("rejected", reason="bad_token", origin=origin or "")
            await ws.close(code=http.WS_1008_POLICY_VIOLATION)
            return
        await ws.accept()
        await hub.add(ws)
        limiter = RateLimiter()
        await ws.send_text(Ready(version=__version__, demo=demo).model_dump_json())
        if core.locked:
            await ws.send_text(Locked(reasons=sorted(core.locks)).model_dump_json())
        await ws.send_text(core.brain_status().model_dump_json())
        await ws.send_text(core.voice_state.model_dump_json())
        try:
            while True:
                raw = await ws.receive_text()
                if len(raw) > 16_384 or not limiter.allow():
                    audit.append("rejected", reason="rate_or_size")
                    await ws.send_text(
                        ErrorEvent(
                            code="rate_limited", message="Too many commands"
                        ).model_dump_json()
                    )
                    continue
                try:
                    cmd = ui_command_adapter.validate_json(raw)
                except ValidationError as e:
                    err = ErrorEvent(code="bad_command", message=str(e.errors()[0]["msg"]))
                    await ws.send_text(err.model_dump_json())
                    continue
                await core.handle(cmd)
        except WebSocketDisconnect:
            pass
        finally:
            await hub.remove(ws)

    return app
