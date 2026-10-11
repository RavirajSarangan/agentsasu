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
from typing import Literal

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


Role = Literal["owner", "family", "kid"]


@dataclass
class Profile:
    """One enrolled person: who they are, what they may do, and their voiceprint."""

    name: str
    role: Role
    voiceprint: Voiceprint


def identify(profiles: Sequence[Profile], embedding: Vector) -> tuple[Profile | None, float]:
    """The best-matching enrolled person above their threshold, and the best score seen."""
    best: Profile | None = None
    best_score = 0.0
    for p in profiles:
        v = p.voiceprint.verify(embedding)
        if v.score > best_score:
            best_score = v.score
            best = p if v.ok else None
    return best, best_score


class VoiceprintVault:
    """AES-256-GCM encrypted file; the key lives in the macOS Keychain (via the shell).

    Holds every enrolled person. Files from before family profiles (a single
    centroid) are read as one "owner" profile.
    """

    AAD = b"sasu-voiceprint-v1"

    def __init__(self, path: Path, key_hex: str) -> None:
        self.path = path
        self._aead = AESGCM(bytes.fromhex(key_hex))

    @property
    def aead(self) -> AESGCM:
        """The vault cipher, shared with other encrypted stores (memory)."""
        return self._aead

    def _write(self, body: dict[str, object]) -> None:
        nonce = os.urandom(12)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(nonce + self._aead.encrypt(nonce, json.dumps(body).encode(), self.AAD))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def save_profiles(self, profiles: Sequence[Profile]) -> None:
        self._write(
            {
                "profiles": [
                    {
                        "name": p.name,
                        "role": p.role,
                        "centroid": p.voiceprint.centroid,
                        "threshold": p.voiceprint.threshold,
                    }
                    for p in profiles
                ]
            }
        )

    def load_profiles(self) -> list[Profile]:
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        body = json.loads(self._aead.decrypt(raw[:12], raw[12:], self.AAD))
        if "profiles" not in body:  # single-owner file from v0.2/v0.3
            return [
                Profile(
                    "Owner", "owner", Voiceprint(list(body["centroid"]), float(body["threshold"]))
                )
            ]
        return [
            Profile(
                str(p["name"]), p["role"], Voiceprint(list(p["centroid"]), float(p["threshold"]))
            )
            for p in body["profiles"]
        ]

    def upsert(self, profile: Profile) -> list[Profile]:
        profiles = [p for p in self.load_profiles() if p.name.lower() != profile.name.lower()]
        profiles.append(profile)
        self.save_profiles(profiles)
        return profiles

    def remove(self, name: str) -> list[Profile]:
        profiles = [p for p in self.load_profiles() if p.name.lower() != name.lower()]
        self.save_profiles(profiles)
        return profiles

    # Back-compat helpers (single owner)
    def save(self, vp: Voiceprint) -> None:
        others = [p for p in self.load_profiles() if p.role != "owner"]
        self.save_profiles([Profile("Owner", "owner", vp), *others])

    def load(self) -> Voiceprint | None:
        owners = [p for p in self.load_profiles() if p.role == "owner"]
        return owners[0].voiceprint if owners else None

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
