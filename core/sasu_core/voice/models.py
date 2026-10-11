"""On-device voice models (sherpa-onnx, no PyTorch). Downloaded once, with consent."""

from __future__ import annotations

import bz2
import tarfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    url: str
    size: int  # bytes to download, for progress
    files: tuple[str, ...]  # what must exist afterwards
    archive: bool = False


MODELS: dict[str, ModelSpec] = {
    "vad": ModelSpec("vad", f"{BASE}/asr-models/silero_vad.onnx", 643_854, ("silero_vad.onnx",)),
    "speaker": ModelSpec(
        "speaker",
        f"{BASE}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34.onnx",
        26_534_365,
        ("wespeaker_en_voxceleb_resnet34.onnx",),
    ),
    "wake": ModelSpec(
        "wake",
        f"{BASE}/asr-models/sherpa-onnx-whisper-tiny.tar.bz2",
        116_204_861,
        ("tiny-encoder.int8.onnx", "tiny-decoder.int8.onnx", "tiny-tokens.txt"),
        archive=True,
    ),
    "stt": ModelSpec(
        "stt",
        f"{BASE}/asr-models/sherpa-onnx-whisper-turbo.tar.bz2",
        563_790_207,
        ("turbo-encoder.int8.onnx", "turbo-decoder.int8.onnx", "turbo-tokens.txt"),
        archive=True,
    ),
}

TOTAL_BYTES = sum(m.size for m in MODELS.values())

Progress = Callable[[int, int, str], None]  # done bytes, total bytes, current model


def ready(models_dir: Path) -> bool:
    return all((models_dir / f).exists() for m in MODELS.values() for f in m.files)


def path(models_dir: Path, name: str) -> str:
    return str(models_dir / name)


def _keep(member: tarfile.TarInfo, wanted: tuple[str, ...]) -> bool:
    return member.isfile() and Path(member.name).name in wanted


def download_all(models_dir: Path, progress: Progress) -> None:
    """Blocking. Fetches whatever is missing; keeps only the int8 files from archives."""
    models_dir.mkdir(parents=True, exist_ok=True)
    done = sum(m.size for m in MODELS.values() if all((models_dir / f).exists() for f in m.files))
    for m in MODELS.values():
        if all((models_dir / f).exists() for f in m.files):
            continue
        tmp = models_dir / (Path(m.url).name + ".part")
        with httpx.stream("GET", m.url, follow_redirects=True, timeout=60) as r:
            r.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
                    done += len(chunk)
                    progress(done, TOTAL_BYTES, m.id)
        if m.archive:
            with bz2.open(tmp) as raw, tarfile.open(fileobj=raw, mode="r|") as tar:
                for member in tar:
                    if _keep(member, m.files):
                        member.name = Path(member.name).name  # flatten, no path tricks
                        tar.extract(member, models_dir, filter="data")
            tmp.unlink()
        else:
            tmp.rename(models_dir / m.files[0])
        missing = [f for f in m.files if not (models_dir / f).exists()]
        if missing:
            raise RuntimeError(f"download of {m.id} is missing {missing}")
