# Contributing to Sasu

Thanks for helping! Tamil and Tanglish speakers are especially welcome: real phrases you say
every day make Sasu better.

## Set up

Requirements: macOS 13+ on Apple Silicon, Node 24 (`nvm use`), pnpm 10, Rust (stable), `uv`.

```bash
pnpm install
pnpm dev            # desktop app (Tauri) + Python core
pnpm web            # landing site on http://localhost:5173
```

## Before you open a pull request

```bash
cd core && uv run ruff check . && uv run mypy && uv run pytest
cd apps/desktop && npx tsc --noEmit && npx vitest run
```

## Rules that keep Sasu safe

- Every new tool goes through `core/sasu_core/tools/` with a risk level, records how to undo it
  (`journal.record` + `@inverse`) and passes through the `Executor` (policy → approval → audit).
- User data reaches AppleScript **only** through argv (`runtime.applescript`), never pasted into a script.
- Secrets never go in argv, environment variables, logs or the WebSocket.
- Tests must use the fake runner (`tests/conftest.py`) so they never touch your real Mac.
- The protocol lives in `core/sasu_core/protocol.py`; run `pnpm protocol:gen` after changing it.

## Good first issues

- Add Tamil / Tanglish phrases to `core/sasu_core/fastpath.py` (with a test).
- Add a festival to `core/sasu_core/extras.py`.
- New sound pack in `packages/brand/src/packs.ts`.

By contributing you agree your work is released under the MIT License.
