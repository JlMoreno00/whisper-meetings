from __future__ import annotations

import json
from datetime import datetime

from whisper_meetings.server import output_base_dir, persist_session


def test_output_base_dir_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WHISPER_MEETINGS_OUTPUT_DIR", str(tmp_path))

    assert output_base_dir() == tmp_path


def test_persist_session_writes_wav_and_json(monkeypatch, tmp_path):
    monkeypatch.setenv("WHISPER_MEETINGS_OUTPUT_DIR", str(tmp_path))
    started_at = datetime(2026, 2, 20, 9, 30, 0)
    pcm = (b"\x00\x00") * 1600
    messages = [
        {
            "segment_id": 0,
            "timestamp": "09:30",
            "speaker": "Locutor",
            "text": "Hola equipo",
        }
    ]

    saved = persist_session(started_at, pcm, messages, "Reunion diaria")

    transcript_path = tmp_path / "20260220-093000" / "transcript.json"
    audio_path = tmp_path / "20260220-093000" / "audio.wav"

    assert saved["transcript_path"] == str(transcript_path)
    assert saved["audio_path"] == str(audio_path)
    assert transcript_path.exists()
    assert audio_path.exists()

    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert payload["meeting_title"] == "Reunion diaria"
    assert payload["sample_rate"] == 16000
    assert payload["transcript"] == messages
