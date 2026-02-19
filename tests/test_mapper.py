"""Tests for schema mapper: mlx-whisper output → TranscriptionResult."""

import json
from pathlib import Path

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# Load fixtures once at module level for reuse
def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_map_transcription_happy_path():
    """Full mlx-whisper output with words → valid TranscriptionResult."""
    from whisper_meetings.mapper import map_transcription

    raw = _load_fixture("mock_mlx_output.json")
    result = map_transcription(raw, "reunion.mp3", 15234567, 5.2, 1.3)

    assert result is not None
    assert result.metadata.file == "reunion.mp3"
    assert result.metadata.file_size_bytes == 15234567
    assert result.metadata.duration_seconds == 5.2
    assert result.metadata.transcription_time_seconds == 1.3
    assert len(result.segments) == 1
    assert len(result.segments[0].words) == 6


# ---------------------------------------------------------------------------
# probability → confidence rename
# ---------------------------------------------------------------------------


def test_map_probability_to_confidence():
    """Raw probability field must be renamed to confidence in output."""
    from whisper_meetings.mapper import map_transcription

    raw = _load_fixture("mock_mlx_output.json")
    result = map_transcription(raw, "test.mp3", 1000, 5.2, 0.5)

    d = result.to_dict()
    words = d["segments"][0]["words"]
    assert len(words) == 6

    for word in words:
        assert "confidence" in word, f"Missing 'confidence' key in word: {word}"
        assert "probability" not in word, (
            f"'probability' must be renamed, found in: {word}"
        )

    # Check specific value preserved correctly
    assert words[0]["confidence"] == 0.92
    assert words[1]["confidence"] == 0.87


# ---------------------------------------------------------------------------
# Empty segments (silent audio)
# ---------------------------------------------------------------------------


def test_map_empty_segments():
    """Silent audio (segments=[]) → valid TranscriptionResult with empty segments."""
    from whisper_meetings.mapper import map_transcription

    raw = _load_fixture("mock_mlx_output_empty.json")
    result = map_transcription(raw, "silent.mp3", 500, 0.5, 0.1)

    assert result.segments == []
    d = result.to_dict()
    assert d["segments"] == []
    # Must be JSON-serializable
    json.dumps(d)


# ---------------------------------------------------------------------------
# Segments without words (word_timestamps=False fallback)
# ---------------------------------------------------------------------------


def test_map_segments_without_words():
    """Segments missing 'words' field → words defaults to empty list."""
    from whisper_meetings.mapper import map_transcription

    raw = _load_fixture("mock_mlx_output_no_words.json")
    result = map_transcription(raw, "test.mp3", 1000, 5.2, 0.5)

    assert len(result.segments) == 1
    assert result.segments[0].words == []


# ---------------------------------------------------------------------------
# All segment fields preserved
# ---------------------------------------------------------------------------


def test_map_preserves_all_segment_fields():
    """Segment fields avg_logprob and no_speech_prob are copied correctly."""
    from whisper_meetings.mapper import map_transcription

    raw = _load_fixture("mock_mlx_output.json")
    result = map_transcription(raw, "test.mp3", 1000, 5.2, 0.5)

    seg = result.segments[0]
    assert seg.id == 0
    assert seg.start == 0.0
    assert seg.end == 5.2
    assert seg.text == "Hola, bienvenidos a la reunión semanal."
    assert abs(seg.avg_logprob - (-0.234)) < 1e-9
    assert abs(seg.no_speech_prob - 0.012) < 1e-9


# ---------------------------------------------------------------------------
# Metadata populated correctly
# ---------------------------------------------------------------------------


def test_map_metadata_populated():
    """All metadata fields are filled after mapping."""
    from whisper_meetings.mapper import map_transcription

    raw = _load_fixture("mock_mlx_output.json")
    result = map_transcription(raw, "reunion.mp3", 15234567, 3600.5, 245.3)

    m = result.metadata
    assert m.file == "reunion.mp3"
    assert m.file_size_bytes == 15234567
    assert m.duration_seconds == 3600.5
    assert m.transcription_time_seconds == 245.3
    assert m.language == "es"
    assert m.model == "mlx-community/whisper-large-v3-mlx"
    # created_at must be ISO 8601 ending with "Z"
    assert m.created_at.endswith("Z"), f"created_at must end with Z: {m.created_at}"
    assert "T" in m.created_at, f"created_at must be ISO format: {m.created_at}"


# ---------------------------------------------------------------------------
# Language fallback
# ---------------------------------------------------------------------------


def test_map_language_fallback_when_missing():
    """If raw_result has no 'language' key, defaults to 'es'."""
    from whisper_meetings.mapper import map_transcription

    raw = {"text": "", "segments": []}  # no "language" key
    result = map_transcription(raw, "test.mp3", 100, 0.0, 0.0)

    assert result.metadata.language == "es"


def test_map_language_taken_from_raw_result():
    """Language field is taken from raw_result when present."""
    from whisper_meetings.mapper import map_transcription

    raw = {"text": "Hello", "segments": [], "language": "en"}
    result = map_transcription(raw, "test.mp3", 100, 0.0, 0.0)

    assert result.metadata.language == "en"
