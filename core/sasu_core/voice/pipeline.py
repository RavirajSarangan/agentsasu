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
Mode = Literal["idle", "command", "speaking", "enroll", "meeting"]


@dataclass
class Heard:
    text: str
    lang: str
    embedding: list[float] | None
    seconds: float


class Callbacks:
    async def on_wake(self, command_follows: bool) -> None: ...
    async def on_command(self, heard: Heard) -> None: ...
    async def on_stop(self) -> None: ...
    async def on_level(self, rms: float) -> None: ...
    async def on_enroll_sample(self, embedding: list[float]) -> None: ...
    async def on_timeout(self) -> None: ...
    async def on_caption(self, text: str, lang: str) -> None: ...


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
        vad_cfg.silero_vad.min_silence_duration = 0.4
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
            tokens=p("turbo-tokens.txt"), language="", num_threads=8,
        )  # fmt: skip
        self._turbo_en: Any = None
        self._forced: dict[str, Any] = {}  # (model, lang) recognizers built on demand
        # The language you mostly speak; used when Whisper guesses a third language.
        self.prefer_lang = "en"
        # Extra robot names the owner chose ("Chitti", "சிட்டி"); "Sasu" always works.
        self.wake_names: tuple[str, ...] = ()
        # Woken in Tamil → decode the next command as Tamil.
        self.next_lang: str | None = None
        self._turbo_args = dict(
            encoder=p("turbo-encoder.int8.onnx"), decoder=p("turbo-decoder.int8.onnx"),
            tokens=p("turbo-tokens.txt"), num_threads=8,
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
        self.arm_timeout = 8.0
        # After Sasu finishes speaking, keep listening for a follow-up (no wake word).
        self.follow_up = False
        self.follow_timeout = 6.0
        self._warm_up()

    def _warm_up(self) -> None:
        """Run each model once so the first real command isn't slow."""
        noise = (np.random.default_rng(0).standard_normal(SR // 2) * 0.01).astype(np.float32)
        for rec in (self.tiny, self.turbo):
            s = rec.create_stream()
            s.accept_waveform(SR, noise)
            rec.decode_stream(s)
        self._embed(np.concatenate([noise, noise]))

    def warm_tamil(self) -> None:
        """Build the Tamil-forced models up front so Tamil commands are as fast as English."""
        noise = (np.random.default_rng(1).standard_normal(SR // 2) * 0.01).astype(np.float32)
        for model in ("tiny", "turbo"):
            self.decode_as(model, "ta", noise)

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
        self.loop.run_in_executor(None, self.warm_tamil)

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

    def arm(self, timeout: float = 8.0) -> None:
        """Treat the next utterance as a command (wake word, hotkey, click, follow-up)."""
        self.mode = "command"
        self.armed_at = time.monotonic()
        self.arm_timeout = timeout
        self.vad.reset()

    def set_speaking(self, speaking: bool) -> None:
        if self.mode == "meeting":
            return  # meetings keep transcribing; Sasu stays quiet anyway
        if speaking:
            self.mode = "speaking"
        elif self.mode == "speaking":
            if self.follow_up:
                self.follow_up = False
                self.arm(self.follow_timeout)
            else:
                self.mode = "idle"
                self.vad.reset()

    def set_meeting(self, on: bool) -> None:
        """Meeting notes: every utterance becomes a caption, no wake word."""
        self.mode = "meeting" if on else "idle"
        self.follow_up = False
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
            # Whisper sometimes guesses a third language ("ja" for "Sasu", "id" for "satham
            # kurai"). Sasu speaks English and Tamil, so decode again in the preferred one.
            lang = self.prefer_lang if self.prefer_lang in ("en", "ta") else "en"
            return self.decode_as("turbo", lang, samples), lang
        return text, _lang(raw, text)

    def _recognizer(self, model: str, lang: str) -> Any:
        import sherpa_onnx as so

        key = f"{model}:{lang}"
        if key not in self._forced:
            args = dict(self._turbo_args)
            if model == "tiny":
                args.update(
                    encoder=str(args["encoder"]).replace("turbo", "tiny"),
                    decoder=str(args["decoder"]).replace("turbo", "tiny"),
                    tokens=str(args["tokens"]).replace("turbo", "tiny"),
                    num_threads=2,
                )
            self._forced[key] = so.OfflineRecognizer.from_whisper(language=lang, **args)
        return self._forced[key]

    def decode_as(self, model: str, lang: str, samples: np.ndarray) -> str:
        rec = self._recognizer(model, lang)
        with self._lock:
            s = rec.create_stream()
            s.accept_waveform(SR, samples)
            rec.decode_stream(s)
            return str(s.result.text).strip()

    def feed(self, samples: np.ndarray) -> None:
        """Push audio as if it came from the mic (tests, file input)."""
        for i in range(0, len(samples), 1024):
            self._offer(samples[i : i + 1024])

    def run_without_mic(self) -> None:
        self._task = self.loop.create_task(self._run())

    def _embed(self, samples: np.ndarray) -> list[float] | None:
        if len(samples) < SR * 0.5:
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
        if self.mode == "meeting":
            text, lang = await run(None, self._decode, self.turbo, samples)
            if text:
                await self.cb.on_caption(text, lang)
            return
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
            if self.next_lang == "ta":
                self.next_lang = None
                text = await run(None, self.decode_as, "turbo", "ta", samples)
                lang = "ta"
            else:
                text, lang = await run(None, self._decode, self.turbo, samples)
            if not text:
                self.arm(self.arm_timeout)
                return
            heard, rest = find_wake(text, self.wake_names)
            if heard and len(rest.split()) == 0:
                # "Hey Sasu" again: still listening, not a command.
                self.arm()
                await self.cb.on_wake(command_follows=False)
                return
            emb = await run(None, self._embed, samples)
            await self.cb.on_command(Heard(rest if heard and rest else text, lang, emb, secs))
            return
        # idle: wake word, possibly with the command in the same breath
        if secs > 12:
            return
        if secs > 1.8:
            # Long enough to hold a command too: one accurate pass instead of two.
            text, lang = await run(None, self._decode, self.turbo, samples)
            heard, rest = find_wake(text, self.wake_names)
            if not heard:
                return
        else:
            quick, qlang = await run(None, self._decode, self.tiny, samples)
            heard, rest = find_wake(quick, self.wake_names)
            if not heard:
                # Short Tamil "சாசு" often gets mis-detected as another language: try as Tamil.
                quick = await run(None, self.decode_as, "tiny", "ta", samples)
                heard, rest = find_wake(quick, self.wake_names)
                qlang = "ta"
                if not heard:
                    return
            if qlang == "ta" or any("\u0b80" <= c <= "\u0bff" for c in quick):
                self.next_lang = "ta"
            text, lang = quick, "ta" if self.next_lang == "ta" else "en"
            if len(rest.split()) >= 2:
                text, lang = await run(None, self._decode, self.turbo, samples)
                _, rest = find_wake(text, self.wake_names)
        if len(rest.split()) >= 1:
            emb = await run(None, self._embed, samples)
            await self.cb.on_wake(command_follows=True)
            await self.cb.on_command(Heard(rest, lang, emb, secs))
        else:
            self.arm()
            await self.cb.on_wake(command_follows=False)


Factory = Callable[[Path, Callbacks, asyncio.AbstractEventLoop], VoicePipeline]
Awaitable_ = Awaitable  # re-export for typing convenience
