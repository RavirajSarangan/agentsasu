"""Live microphone → VAD → wake word / command → text, with a speaker check.

Modes:
  idle     listen for "Hey Sasu" (tiny Whisper on short speech segments)
  command  the next utterance is a command (after the wake word, ⌥Space or a click)
  speaking Sasu is talking: only "stop / நிறுத்து" counts (no echo commands)
  enroll   collect voice samples for the owner's voiceprint
"""

from __future__ import annotations

import asyncio
import math
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from . import models
from .wake import find_wake, is_stop

SR = 16_000
Mode = Literal["idle", "command", "speaking", "enroll"]


@dataclass
class Heard:
    text: str
    lang: str
    embedding: list[float] | None
    seconds: float


class Callbacks:
    async def on_wake(self) -> None: ...
    async def on_command(self, heard: Heard) -> None: ...
    async def on_stop(self) -> None: ...
    async def on_level(self, rms: float) -> None: ...
    async def on_enroll_sample(self, embedding: list[float]) -> None: ...
    async def on_timeout(self) -> None: ...


def _lang(raw: Any, text: str) -> str:
    code = str(raw or "").strip("<|>").lower()
    if code in {"ta", "en"}:
        return code
    return "ta" if any("஀" <= c <= "௿" for c in text) else "en"


class VoicePipeline:
    def __init__(self, models_dir: Path, cb: Callbacks, loop: asyncio.AbstractEventLoop) -> None:
        import sherpa_onnx as so

        p = lambda name: models.path(models_dir, name)  # noqa: E731
        vad_cfg = so.VadModelConfig()
        vad_cfg.silero_vad.model = p("silero_vad.onnx")
        vad_cfg.silero_vad.threshold = 0.5
        vad_cfg.silero_vad.min_silence_duration = 0.55
        vad_cfg.silero_vad.min_speech_duration = 0.25
        vad_cfg.silero_vad.max_speech_duration = 15
        vad_cfg.sample_rate = SR
        self.vad = so.VoiceActivityDetector(vad_cfg, buffer_size_in_seconds=30)
        self.window = vad_cfg.silero_vad.window_size

        self.tiny = so.OfflineRecognizer.from_whisper(
            encoder=p("tiny-encoder.int8.onnx"), decoder=p("tiny-decoder.int8.onnx"),
            tokens=p("tiny-tokens.txt"), language="", num_threads=2,
        )  # fmt: skip
        self.turbo = so.OfflineRecognizer.from_whisper(
            encoder=p("turbo-encoder.int8.onnx"), decoder=p("turbo-decoder.int8.onnx"),
            tokens=p("turbo-tokens.txt"), language="", num_threads=4,
        )  # fmt: skip
        self._turbo_en: Any = None
        self._turbo_args = dict(
            encoder=p("turbo-encoder.int8.onnx"), decoder=p("turbo-decoder.int8.onnx"),
            tokens=p("turbo-tokens.txt"), num_threads=4,
        )  # fmt: skip
        spk_cfg = so.SpeakerEmbeddingExtractorConfig(
            model=p("wespeaker_en_voxceleb_resnet34.onnx"), num_threads=2
        )
        self.speaker = so.SpeakerEmbeddingExtractor(spk_cfg)

        self.cb = cb
        self.loop = loop
        self.mode: Mode = "idle"
        self.armed_at = 0.0
        self._buf = np.zeros(0, dtype=np.float32)
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=200)
        self._stream: Any = None
        self._task: asyncio.Task[None] | None = None
        self._lock = threading.Lock()
        self._last_level = 0.0
        self._overflow: list[np.ndarray] = []

    # ── control ────────────────────────────────────────────────────────────
    def start(self) -> None:
        import sounddevice as sd

        def callback(indata: np.ndarray, frames: int, t: Any, status: Any) -> None:
            data = indata[:, 0].copy()
            self.loop.call_soon_threadsafe(self._offer, data)

        self._stream = sd.InputStream(
            samplerate=SR, channels=1, dtype="float32", blocksize=1024, callback=callback
        )
        self._stream.start()
        self._task = self.loop.create_task(self._run())

    def _offer(self, data: np.ndarray) -> None:
        if not self._queue.full():
            self._queue.put_nowait(data)
        elif self._stream is None:  # file input: don't drop audio
            self._overflow.append(data)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._task:
            self._task.cancel()

    def arm(self) -> None:
        """Treat the next utterance as a command (wake word, hotkey or click)."""
        self.mode = "command"
        self.armed_at = time.monotonic()
        self.vad.reset()

    def set_speaking(self, speaking: bool) -> None:
        if speaking:
            self.mode = "speaking"
        elif self.mode == "speaking":
            self.mode = "idle"
            self.vad.reset()

    def set_enroll(self, on: bool) -> None:
        self.mode = "enroll" if on else "idle"
        self.vad.reset()

    # ── processing ─────────────────────────────────────────────────────────
    def _decode(self, rec: Any, samples: np.ndarray) -> tuple[str, str]:
        with self._lock:
            s = rec.create_stream()
            s.accept_waveform(SR, samples)
            rec.decode_stream(s)
            text = s.result.text.strip()
            raw = str(getattr(s.result, "lang", "")).strip("<|>").lower()
        if (
            rec is self.turbo
            and raw
            and raw not in {"en", "ta"}
            and not any("\u0b80" <= c <= "\u0bff" for c in text)
        ):
            # Whisper sometimes guesses a third language (e.g. "es" for "Hey Sasu"); Sasu only
            # speaks English and Tamil, so decode again as English.
            return self._decode_en(samples), "en"
        return text, _lang(raw, text)

    def _decode_en(self, samples: np.ndarray) -> str:
        import sherpa_onnx as so

        if self._turbo_en is None:
            self._turbo_en = so.OfflineRecognizer.from_whisper(language="en", **self._turbo_args)
        with self._lock:
            s = self._turbo_en.create_stream()
            s.accept_waveform(SR, samples)
            self._turbo_en.decode_stream(s)
            return str(s.result.text).strip()

    def feed(self, samples: np.ndarray) -> None:
        """Push audio as if it came from the mic (tests, file input)."""
        for i in range(0, len(samples), 1024):
            self._offer(samples[i : i + 1024])

    def run_without_mic(self) -> None:
        self._task = self.loop.create_task(self._run())

    def _embed(self, samples: np.ndarray) -> list[float] | None:
        if len(samples) < SR * 0.8:
            return None
        with self._lock:
            s = self.speaker.create_stream()
            s.accept_waveform(sample_rate=SR, waveform=samples)
            s.input_finished()
            if not self.speaker.is_ready(s):
                return None
            return list(self.speaker.compute(s))

    async def _run(self) -> None:
        while True:
            data = await self._queue.get()
            if self._overflow and not self._queue.full():
                self._queue.put_nowait(self._overflow.pop(0))
            await self._level(data)
            if (
                self.mode == "command"
                and time.monotonic() - self.armed_at > 8
                and not self.vad.is_speech_detected()
            ):
                self.mode = "idle"
                await self.cb.on_timeout()
            self._buf = np.concatenate([self._buf, data])
            while len(self._buf) >= self.window:
                self.vad.accept_waveform(self._buf[: self.window])
                self._buf = self._buf[self.window :]
            while not self.vad.empty():
                samples = np.array(self.vad.front.samples, dtype=np.float32)
                self.vad.pop()
                await self._segment(samples)

    async def _level(self, data: np.ndarray) -> None:
        now = time.monotonic()
        if self.mode in ("command", "enroll") and now - self._last_level > 0.08:
            self._last_level = now
            rms = float(np.sqrt(np.mean(data**2)))
            await self.cb.on_level(min(1.0, math.sqrt(rms) * 2.2))

    async def _segment(self, samples: np.ndarray) -> None:
        secs = len(samples) / SR
        run = self.loop.run_in_executor
        if self.mode == "speaking":
            if secs < 3:
                text, _ = await run(None, self._decode, self.tiny, samples)
                if is_stop(text):
                    await self.cb.on_stop()
            return
        if self.mode == "enroll":
            emb = await run(None, self._embed, samples)
            if emb:
                await self.cb.on_enroll_sample(emb)
            return
        if self.mode == "command":
            self.mode = "idle"
            text, lang = await run(None, self._decode, self.turbo, samples)
            emb = await run(None, self._embed, samples)
            if text:
                await self.cb.on_command(Heard(text, lang, emb, secs))
            return
        # idle: wake word, possibly with the command in the same breath
        if secs > 12:
            return
        quick, _ = await run(None, self._decode, self.tiny, samples)
        heard, rest = find_wake(quick)
        if not heard:
            return
        if len(rest.split()) >= 2:
            text, lang = await run(None, self._decode, self.turbo, samples)
            _, cmd = find_wake(text)
            emb = await run(None, self._embed, samples)
            await self.cb.on_wake()
            await self.cb.on_command(Heard(cmd or text, lang, emb, secs))
        else:
            self.arm()
            await self.cb.on_wake()


Factory = Callable[[Path, Callbacks, asyncio.AbstractEventLoop], VoicePipeline]
Awaitable_ = Awaitable  # re-export for typing convenience
