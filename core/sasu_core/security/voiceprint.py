"""Owner-only voice: compare each utterance's speaker embedding with the enrolled owner.

The embedding model (ECAPA-TDNN, local ONNX) arrives with the audio pipeline in
Phase 2. This module holds the maths and the encrypted storage so the rest of the
core can already depend on `Voiceprint.verify()`. Embeddings never leave the device.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_THRESHOLD = 0.68  # cosine; measured: same voice ≈0.80, other voices 0.46–0.62
MIN_ENROLL_SAMPLES = 3

Vector = Sequence[float]


def _norm(v: Vector) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    if n == 0:
        raise ValueError("zero vector")
    return [x / n for x in v]


def cosine(a: Vector, b: Vector) -> float:
    if len(a) != len(b):
        raise ValueError("embedding size mismatch")
    return sum(x * y for x, y in zip(_norm(a), _norm(b), strict=True))


@dataclass
class Verdict:
    ok: bool
    score: float


@dataclass
class Voiceprint:
    centroid: list[float]
    threshold: float = DEFAULT_THRESHOLD

    @classmethod
    def enroll(cls, samples: Sequence[Vector], threshold: float = DEFAULT_THRESHOLD) -> Voiceprint:
        if len(samples) < MIN_ENROLL_SAMPLES:
            raise ValueError(f"need at least {MIN_ENROLL_SAMPLES} samples")
        normed = [_norm(s) for s in samples]
        dim = len(normed[0])
        centroid = [sum(s[i] for s in normed) / len(normed) for i in range(dim)]
        return cls(_norm(centroid), threshold)

    def verify(self, embedding: Vector) -> Verdict:
        score = cosine(self.centroid, embedding)
        return Verdict(ok=score >= self.threshold, score=round(score, 4))


class VoiceprintVault:
    """AES-256-GCM encrypted file; the key lives in the macOS Keychain (via the shell)."""

    def __init__(self, path: Path, key_hex: str) -> None:
        self.path = path
        self._aead = AESGCM(bytes.fromhex(key_hex))

    def save(self, vp: Voiceprint) -> None:
        nonce = os.urandom(12)
        body = json.dumps({"centroid": vp.centroid, "threshold": vp.threshold}).encode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(nonce + self._aead.encrypt(nonce, body, b"sasu-voiceprint-v1"))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def load(self) -> Voiceprint | None:
        if not self.path.exists():
            return None
        raw = self.path.read_bytes()
        body = json.loads(self._aead.decrypt(raw[:12], raw[12:], b"sasu-voiceprint-v1"))
        return Voiceprint(list(body["centroid"]), float(body["threshold"]))

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
