"""Entry point.

Desktop shell mode (`--stdin-config`): the first stdin line is a JSON StdinConfig
(token, data dir, Keychain vault key), so no secret ever appears in argv or the
environment. Later stdin lines are trusted control messages (lock, unlock, Touch ID
results, kill switch). The first stdout line is the handshake `{"port": 51234}`.
The process exits when stdin closes, so it never outlives the app.

Dev mode (`--token dev --dev`): for running the UI in a plain browser.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import threading
from pathlib import Path

import uvicorn
from pydantic import ValidationError

from .core import Core
from .protocol import StdinConfig, control_adapter
from .server import create_app

DEFAULT_DATA = Path.home() / "Library" / "Application Support" / "Sasu-dev"


def _read_control(core: Core, loop: asyncio.AbstractEventLoop) -> None:
    for line in sys.stdin:
        try:
            msg = control_adapter.validate_json(line)
        except ValidationError:
            print("[core] ignored bad control line", file=sys.stderr, flush=True)
            continue
        asyncio.run_coroutine_threadsafe(core.control(msg), loop)
    os._exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(prog="sasu-core")
    parser.add_argument("--port", type=int, default=0, help="0 picks a free port")
    parser.add_argument("--stdin-config", action="store_true", help="read secrets from stdin")
    parser.add_argument("--token", default=None, help="dev only: fixed token")
    parser.add_argument("--dev", action="store_true", help="allow the Vite dev origin")
    parser.add_argument("--demo", action="store_true", help="cycle scripted turns")
    parser.add_argument("--delay", type=float, default=1.0, help="demo step delay (s)")
    args = parser.parse_args()

    if args.stdin_config:
        cfg = StdinConfig.model_validate_json(sys.stdin.readline())
        token, data_dir, vault_key, dev = cfg.token, Path(cfg.data_dir), cfg.vault_key, cfg.dev
    elif args.token:
        token, data_dir, vault_key, dev = args.token, DEFAULT_DATA, None, True
    else:
        parser.error("use --stdin-config (app) or --token (dev)")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", args.port))
    print(json.dumps({"port": sock.getsockname()[1]}), flush=True)

    app = create_app(
        token,
        data_dir=data_dir,
        vault_key=vault_key,
        demo=args.demo,
        delay=args.delay,
        dev=dev or args.dev,
    )
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))

    async def run() -> None:
        if args.stdin_config:
            loop = asyncio.get_running_loop()
            threading.Thread(target=_read_control, args=(app.state.core, loop), daemon=True).start()
        await server.serve(sockets=[sock])

    asyncio.run(run())


if __name__ == "__main__":
    main()
