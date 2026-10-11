## What changed

## How I tested it

- [ ] `uv run ruff check . && uv run mypy && uv run pytest` (core)
- [ ] `npx tsc --noEmit && npx vitest run` (apps/desktop)
- [ ] New tools go through the Executor, record undo, and pass user data to AppleScript only via argv
