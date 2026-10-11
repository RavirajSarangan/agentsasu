#!/usr/bin/env bash
# Build Sasu.app and the styled DMG (Apple Silicon).
#   scripts/release-mac.sh
# Needs: Node 24 (nvm), pnpm, Rust, uv. The DMG layout is written by appdmg, which
# doesn't need to script Finder (Tauri's own DMG step can silently lose the layout).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/apps/desktop/src-tauri/target/release/bundle"

(cd "$ROOT/core" && uv run --with pyinstaller python build_sidecar.py)
(cd "$ROOT" && pnpm build)

SPEC="$(mktemp -d)/dmg.json"
cat > "$SPEC" <<JSON
{
  "title": "Sasu",
  "icon": "$ROOT/apps/desktop/src-tauri/icons/icon.icns",
  "background": "$ROOT/assets/dmg-background.png",
  "icon-size": 88,
  "window": { "size": { "width": 660, "height": 400 } },
  "format": "ULFO",
  "contents": [
    { "x": 180, "y": 220, "type": "file", "path": "$OUT/macos/Sasu.app" },
    { "x": 480, "y": 220, "type": "link", "path": "/Applications" }
  ]
}
JSON
rm -f "$OUT/dmg/Sasu-mac.dmg"
npx --yes appdmg@0.6.6 "$SPEC" "$OUT/dmg/Sasu-mac.dmg"
codesign --verify --deep --strict "$OUT/macos/Sasu.app"
echo "→ $OUT/dmg/Sasu-mac.dmg"
