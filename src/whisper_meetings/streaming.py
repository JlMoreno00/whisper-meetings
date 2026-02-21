from __future__ import annotations

import importlib
import re
import threading
import unicodedata
from collections import deque
from dataclasses import dataclass
from typing import Protocol, cast, final

import mlx_whisper
import numpy as np

MODEL_REPO = "mlx-community/whisper-large-v3-turbo"
LANGUAGE = "es"

SAMPLE_RATE = 16000
FRAME_MS = 20
FRAME_SAMPLES = 320
FRAME_BYTES = FRAME_SAMPLES * 2

PRE_ROLL_MS = 300
SILENCE_HANGOVER_MS = 600
MIN_UTTERANCE_MS = 800
MAX_UTTERANCE_MS = 8000
PARTIAL_INTERVAL_MS = 1000
PARTIAL_WINDOW_MS = 2500
MIN_RMS_FOR_TRANSCRIPTION = 90.0
MIN_RMS_FOR_KNOWN_HALLUCINATIONS = 230.0
NO_SPEECH_SUPPRESS_THRESHOLD = 0.78
NO_SPEECH_HALLUCINATION_THRESHOLD = 0.45

KNOWN_LOW_ENERGY_HALLUCINATIONS = {
    "gracias",
    "gracias!",
    "gracias por ver",
    "suscribete",
    "suscribete al canal",
    "suscribete a mi canal",
    "suscribete a nuestro canal",
}

_model_warm_lock = threading.Lock()
_model_warm = False


@dataclass
class SegmentTask:
    kind: str
    segment_id: int
    pcm_bytes: bytes


class VAD(Protocol):
    def is_speech(self, frame: bytes, sample_rate: int) -> bool: ...


def _ensure_pkg_resources() -> None:
    """Shim pkg_resources if missing (setuptools >=72 removed it).

    webrtcvad uses ``import pkg_resources`` only to retrieve its own
    version string at import time.  We provide a minimal stub so that
    the import succeeds without pinning an ancient setuptools.
    """
    import sys

    if "pkg_resources" not in sys.modules:
        try:
            importlib.import_module("pkg_resources")
        except ModuleNotFoundError:
            import types

            _stub = types.ModuleType("pkg_resources")

            class _FakeDist:
                version = "0.0.0"

            setattr(_stub, "get_distribution", lambda _name: _FakeDist())
            sys.modules["pkg_resources"] = _stub


def create_vad(mode: int) -> VAD:
    _ensure_pkg_resources()
    module = importlib.import_module("webrtcvad")
    vad_ctor = getattr(module, "Vad", None)
    if vad_ctor is None:
        raise RuntimeError("webrtcvad.Vad is not available")

    vad_obj = vad_ctor(mode)
    if not hasattr(vad_obj, "is_speech"):
        raise RuntimeError("Invalid webrtcvad instance")

    return cast(VAD, vad_obj)


@final
class VADSegmenter:
    def __init__(self, vad_mode: int = 2) -> None:
        self.vad: VAD = create_vad(vad_mode)
        self.pre_roll_frames: int = PRE_ROLL_MS // FRAME_MS
        self.silence_hangover_frames: int = SILENCE_HANGOVER_MS // FRAME_MS
        self.min_utterance_frames: int = MIN_UTTERANCE_MS // FRAME_MS
        self.max_utterance_frames: int = MAX_UTTERANCE_MS // FRAME_MS
        self.partial_interval_frames: int = PARTIAL_INTERVAL_MS // FRAME_MS
        self.partial_window_frames: int = PARTIAL_WINDOW_MS // FRAME_MS

        self._pre_roll: deque[bytes] = deque(maxlen=self.pre_roll_frames)
        self._speech_frames: list[bytes] = []
        self._in_speech: bool = False
        self._silence_run: int = 0
        self._last_partial_at: int = 0
        self._segment_id: int = 0

    def reset(self) -> None:
        self._pre_roll.clear()
        self._speech_frames = []
        self._in_speech = False
        self._silence_run = 0
        self._last_partial_at = 0

    def push_frame(self, frame: bytes) -> list[SegmentTask]:
        if len(frame) != FRAME_BYTES:
            raise ValueError(
                f"Invalid frame size: expected {FRAME_BYTES} bytes, got {len(frame)}"
            )

        is_speech = self.vad.is_speech(frame, SAMPLE_RATE)
        self._pre_roll.append(frame)
        tasks: list[SegmentTask] = []

        if not self._in_speech:
            if is_speech:
                self._start_utterance()
            return tasks

        self._speech_frames.append(frame)

        if is_speech:
            self._silence_run = 0
        else:
            self._silence_run += 1

        utterance_len = len(self._speech_frames)

        if (
            utterance_len >= self.min_utterance_frames
            and utterance_len - self._last_partial_at >= self.partial_interval_frames
        ):
            partial_pcm = self._window_pcm_bytes()
            tasks.append(
                SegmentTask(
                    kind="partial",
                    segment_id=self._segment_id,
                    pcm_bytes=partial_pcm,
                )
            )
            self._last_partial_at = utterance_len

        if self._silence_run >= self.silence_hangover_frames:
            final_task = self._finalize_utterance()
            if final_task is not None:
                tasks.append(final_task)
            return tasks

        if utterance_len >= self.max_utterance_frames:
            final_task = self._finalize_utterance(force=True)
            if final_task is not None:
                tasks.append(final_task)

        return tasks

    def flush(self) -> list[SegmentTask]:
        if not self._in_speech:
            return []
        final_task = self._finalize_utterance(force=True)
        return [final_task] if final_task is not None else []

    def _start_utterance(self) -> None:
        self._in_speech = True
        self._silence_run = 0
        self._last_partial_at = 0
        self._speech_frames = list(self._pre_roll)

    def _window_pcm_bytes(self) -> bytes:
        window = self._speech_frames[-self.partial_window_frames :]
        return b"".join(window)

    def _finalize_utterance(self, force: bool = False) -> SegmentTask | None:
        utterance_len = len(self._speech_frames)
        if utterance_len < self.min_utterance_frames and not force:
            self._in_speech = False
            self._speech_frames = []
            self._silence_run = 0
            return None

        if utterance_len < self.min_utterance_frames:
            self._in_speech = False
            self._speech_frames = []
            self._silence_run = 0
            return None

        task = SegmentTask(
            kind="final",
            segment_id=self._segment_id,
            pcm_bytes=b"".join(self._speech_frames),
        )

        self._segment_id += 1
        self._in_speech = False
        self._speech_frames = []
        self._silence_run = 0
        self._last_partial_at = 0
        return task


def transcribe_pcm_bytes(pcm_bytes: bytes) -> str:
    pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
    if pcm_int16.size == 0:
        return ""

    rms = float(np.sqrt(np.mean(np.square(pcm_int16.astype(np.float32)))))
    if rms < MIN_RMS_FOR_TRANSCRIPTION:
        return ""

    audio_float = pcm_int16.astype(np.float32) / 32768.0
    try:
        raw_obj = mlx_whisper.transcribe(
            audio_float,
            path_or_hf_repo=MODEL_REPO,
            language=LANGUAGE,
            verbose=False,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.7,
            logprob_threshold=-1.0,
            hallucination_silence_threshold=0.5,
        )
    except TypeError:
        raw_obj = mlx_whisper.transcribe(
            audio_float,
            path_or_hf_repo=MODEL_REPO,
            language=LANGUAGE,
            verbose=False,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.7,
            logprob_threshold=-1.0,
        )
    raw = cast(dict[str, object], raw_obj)
    no_speech_prob = _extract_no_speech_prob(raw)

    text_obj = raw.get("text")
    if isinstance(text_obj, str):
        text = text_obj.strip()
        if text:
            return _clean_transcript_text(text, rms, no_speech_prob)

    segments_obj = raw.get("segments")
    segment_texts: list[str] = []
    if isinstance(segments_obj, list):
        for segment in segments_obj:
            if not isinstance(segment, dict):
                continue
            segment_text_obj = segment.get("text")
            if isinstance(segment_text_obj, str):
                segment_texts.append(segment_text_obj.strip())

    combined = " ".join(segment_texts)
    return _clean_transcript_text(combined.strip(), rms, no_speech_prob)


def _extract_no_speech_prob(raw: dict[str, object]) -> float | None:
    probs: list[float] = []

    top_prob = raw.get("no_speech_prob")
    if isinstance(top_prob, (int, float)):
        probs.append(float(top_prob))

    segments_obj = raw.get("segments")
    if isinstance(segments_obj, list):
        for segment in segments_obj:
            if not isinstance(segment, dict):
                continue
            p = segment.get("no_speech_prob")
            if isinstance(p, (int, float)):
                probs.append(float(p))

    if not probs:
        return None

    return sum(probs) / len(probs)


def _normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    without_accents = "".join(
        c
        for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )
    alnum_spaces = re.sub(r"[^a-z0-9\s]+", " ", without_accents)
    return " ".join(alnum_spaces.split())


KNOWN_LOW_ENERGY_HALLUCINATIONS_NORMALIZED = {
    _normalize_text(x) for x in KNOWN_LOW_ENERGY_HALLUCINATIONS
}


def _clean_transcript_text(text: str, rms: float, no_speech_prob: float | None) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    norm = _normalize_text(cleaned)
    if not norm:
        return ""

    if no_speech_prob is not None and no_speech_prob >= NO_SPEECH_SUPPRESS_THRESHOLD:
        return ""

    if norm in KNOWN_LOW_ENERGY_HALLUCINATIONS_NORMALIZED and (
        rms < MIN_RMS_FOR_KNOWN_HALLUCINATIONS
        or (
            no_speech_prob is not None
            and no_speech_prob >= NO_SPEECH_HALLUCINATION_THRESHOLD
        )
    ):
        return ""

    return cleaned


def warmup_transcriber() -> None:
    global _model_warm
    if _model_warm:
        return

    with _model_warm_lock:
        if _model_warm:
            return
        silent = (np.zeros(SAMPLE_RATE, dtype=np.int16)).tobytes()
        _ = transcribe_pcm_bytes(silent)
        _model_warm = True


def title_from_text(text: str, max_words: int = 8) -> str:
    words = [word for word in text.strip().split() if word]
    if not words:
        return ""
    return " ".join(words[:max_words])
