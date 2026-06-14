from __future__ import annotations

import io
import wave

import numpy as np
from faster_whisper import WhisperModel

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def transcrever_wav(wav_bytes: bytes) -> str:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    model = _get_model()
    segments, _ = model.transcribe(audio, language="pt", beam_size=5, vad_filter=True)
    return " ".join(seg.text for seg in segments).strip()
