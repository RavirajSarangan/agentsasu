# Privacy Policy

_Last updated: 11 October 2026_

Sasu is an open-source app that runs on your Mac. There is no Sasu server, no account and no
analytics. This page explains exactly what happens to your data, based on what the code does.

## What stays on your Mac

| Data | Where | Protection |
| --- | --- | --- |
| Microphone audio | Processed in memory, never saved | Wake word and speech-to-text run on-device (Whisper via sherpa-onnx) |
| Voiceprints (you and family) | `voiceprint.bin` | AES-256-GCM, key in the macOS Keychain |
| Memories ("remember…") | `memory.bin` | AES-256-GCM, same key |
| Activity log | `audit.sqlite` | Hash-chained so edits are detectable, file mode 0600 |
| Undo history, skills | `undo.sqlite`, `skills.json` | File mode 0600 |
| Intruder photos (only if you turn it on) | `intruders/` | File mode 0600, folder 0700 |
| Diary, clipboard history (only if you turn it on) | `diary.bin`, `clips.bin` | AES-256-GCM, same key; clipboard history skips codes and passwords |
| Meeting audio | Never saved | Captions are made on-device; only the text becomes notes |
| AI keys | macOS Keychain | Never written to logs or sent anywhere except the provider you chose |

The data folder is `~/Library/Application Support/dev.sasu.desktop/`.

## What leaves your Mac

Only when you ask Sasu something that needs an AI model, and only to the provider **you** picked
(Google Gemini, Groq, Anthropic, or none if you use Ollama locally):

- the **text** of your request, recent conversation, and results of actions Sasu took for it
  (for example a list of file names it found);
- for "what's on my screen?", **one screenshot**, deleted right after it's sent.

Before sending, Sasu removes things that look like passwords, API keys and card numbers.
After every request, the **privacy meter** shows how many characters and images were sent, and to whom.

Audio, voiceprints, memories, photos and the activity log are **never** sent anywhere.

Common requests (music, volume, opening apps, time, briefings) are handled on your Mac without
any AI provider. The morning briefing asks Open-Meteo for the weather of the city you typed in
Settings (no account, no key).

## Third-party providers

When you use a cloud AI provider, their privacy policy applies to what is sent to them. On some
free tiers (for example Google AI Studio), the provider may use your prompts to improve its models.
Use a paid tier or Ollama if that matters to you.

## Children

Kid profiles limit what Sasu can do. Sasu does not collect data about children; voiceprints stay on the Mac.

## Deleting everything

Quit Sasu and delete `~/Library/Application Support/dev.sasu.desktop/`. Remove the AI keys in
Settings → AI brain (or from Keychain Access, service `dev.sasu.desktop.ai`). Trap files Sasu
planted are removed when you turn "Trap files" off.

## Changes

Changes to this policy are made in the public repository, so every change is visible in its history.

## Contact

Open an issue at <https://github.com/RavirajSarangan/agentsasu/issues>.
