# Sasu native core (Swift)

The Python core works, but shipping it means bundling a whole Python runtime (145 MB).
This package is its replacement, built **one piece at a time**. Each piece speaks the same
protocol and file formats as the Python core, and is checked against it by
`core/tests/test_swift_core.py`, so the app never breaks during the move.

| Phase | What | Status |
| --- | --- | --- |
| 1 | Local server (127.0.0.1, token, origin checks, rate limits), stdin control channel, hash-chained audit log (same SQLite file), secret redaction | ✅ done — 268 KB binary |
| 2a | Policy (paths, shell commands incl. a faithful `shlex` port), roles, trap files, leak guard, instant-command parser, undo journal | ✅ done — parity-tested on a large corpus |
| 2b | Tools and the Executor (policy → approval → run → journal → audit), turns over the WebSocket | next |
| 3 | Voice: sherpa-onnx (VAD, Whisper, voiceprint), AVAudioEngine mic, AVSpeechSynthesizer, Touch ID | |
| 4 | AI brain (URLSession, OpenAI-compatible), then the app switches to this core | |
| 5 | Optional: SwiftUI shell, App Intents / Shortcuts | |

```bash
swift build -c release            # needs only the Xcode command-line tools
.build/release/sasu-core-swift --verify-audit ~/Library/Application\ Support/dev.sasu.desktop/audit.sqlite
cd ../../core && uv run pytest tests/test_swift_core.py
```
