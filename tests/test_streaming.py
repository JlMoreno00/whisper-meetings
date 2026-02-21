from __future__ import annotations

import numpy as np

from whisper_meetings import streaming


def _pcm_with_amplitude(amplitude: int, samples: int = 16000) -> bytes:
    data = np.full(samples, amplitude, dtype=np.int16)
    return data.tobytes()


def test_transcribe_pcm_bytes_skips_very_low_energy(monkeypatch):
    called = False

    def _fake_transcribe(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal called
        called = True
        return {"text": "hola"}

    monkeypatch.setattr(streaming.mlx_whisper, "transcribe", _fake_transcribe)

    text = streaming.transcribe_pcm_bytes(_pcm_with_amplitude(20))

    assert text == ""
    assert called is False


def test_transcribe_pcm_bytes_filters_known_low_energy_hallucinations(monkeypatch):
    def _fake_transcribe(*args, **kwargs):  # noqa: ANN002, ANN003
        return {"text": "¡Suscríbete a mi canal!"}

    monkeypatch.setattr(streaming.mlx_whisper, "transcribe", _fake_transcribe)

    text = streaming.transcribe_pcm_bytes(_pcm_with_amplitude(120))

    assert text == ""


def test_transcribe_pcm_bytes_keeps_valid_low_energy_text(monkeypatch):
    def _fake_transcribe(*args, **kwargs):  # noqa: ANN002, ANN003
        return {"text": "hola equipo"}

    monkeypatch.setattr(streaming.mlx_whisper, "transcribe", _fake_transcribe)

    text = streaming.transcribe_pcm_bytes(_pcm_with_amplitude(120))

    assert text == "hola equipo"


def test_transcribe_pcm_bytes_filters_high_no_speech_prob(monkeypatch):
    def _fake_transcribe(*args, **kwargs):  # noqa: ANN002, ANN003
        return {
            "text": "gracias",
            "segments": [
                {
                    "text": "gracias",
                    "no_speech_prob": 0.93,
                }
            ],
        }

    monkeypatch.setattr(streaming.mlx_whisper, "transcribe", _fake_transcribe)

    text = streaming.transcribe_pcm_bytes(_pcm_with_amplitude(500))

    assert text == ""


def test_transcribe_pcm_bytes_uses_non_contextual_decode(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_transcribe(*args, **kwargs):  # noqa: ANN002, ANN003
        captured.update(kwargs)
        return {"text": "hola"}

    monkeypatch.setattr(streaming.mlx_whisper, "transcribe", _fake_transcribe)

    _ = streaming.transcribe_pcm_bytes(_pcm_with_amplitude(500))

    assert captured["temperature"] == 0.0
    assert captured["condition_on_previous_text"] is False
