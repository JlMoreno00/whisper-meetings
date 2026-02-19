"""Tests for JSON output schema dataclasses."""

import json
import pytest
from whisper_meetings.schema import Word, Segment, Metadata, TranscriptionResult


class TestWord:
    """Test Word dataclass."""

    def test_word_creation(self):
        """Word can be created with valid data."""
        word = Word(word="Hola", start=0.0, end=0.4, confidence=0.92)
        assert word.word == "Hola"
        assert word.start == 0.0
        assert word.end == 0.4
        assert word.confidence == 0.92

    def test_word_confidence_float(self):
        """Word.confidence accepts float 0-1."""
        word = Word(word="test", start=0.0, end=0.1, confidence=0.5)
        assert isinstance(word.confidence, float)
        assert 0.0 <= word.confidence <= 1.0


class TestSegment:
    """Test Segment dataclass."""

    def test_segment_creation(self):
        """Segment can be created with valid data."""
        word = Word(word="Hola", start=0.0, end=0.4, confidence=0.92)
        segment = Segment(
            id=0,
            start=0.0,
            end=0.4,
            text="Hola",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[word],
        )
        assert segment.id == 0
        assert segment.text == "Hola"
        assert len(segment.words) == 1
        assert segment.words[0].word == "Hola"

    def test_segment_words_list(self):
        """Segment.words is a list of Word objects."""
        words = [
            Word(word="Hola", start=0.0, end=0.4, confidence=0.92),
            Word(word="mundo", start=0.5, end=1.0, confidence=0.88),
        ]
        segment = Segment(
            id=0,
            start=0.0,
            end=1.0,
            text="Hola mundo",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=words,
        )
        assert len(segment.words) == 2
        assert all(isinstance(w, Word) for w in segment.words)

    def test_segment_empty_words(self):
        """Segment can have empty words list."""
        segment = Segment(
            id=0,
            start=0.0,
            end=0.4,
            text="",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[],
        )
        assert segment.words == []


class TestMetadata:
    """Test Metadata dataclass."""

    def test_metadata_creation(self):
        """Metadata can be created with all required fields."""
        metadata = Metadata(
            file="test.mp3",
            file_size_bytes=1000,
            duration_seconds=10.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=5.0,
            created_at="2026-01-01T00:00:00Z",
        )
        assert metadata.file == "test.mp3"
        assert metadata.file_size_bytes == 1000
        assert metadata.duration_seconds == 10.0
        assert metadata.language == "es"
        assert metadata.model == "mlx-community/whisper-large-v3-turbo"
        assert metadata.transcription_time_seconds == 5.0
        assert metadata.created_at == "2026-01-01T00:00:00Z"


class TestTranscriptionResult:
    """Test TranscriptionResult dataclass."""

    def test_transcription_result_creation(self):
        """TranscriptionResult can be created with metadata and segments."""
        metadata = Metadata(
            file="test.mp3",
            file_size_bytes=1000,
            duration_seconds=10.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=5.0,
            created_at="2026-01-01T00:00:00Z",
        )
        word = Word(word="Hola", start=0.0, end=0.4, confidence=0.92)
        segment = Segment(
            id=0,
            start=0.0,
            end=0.4,
            text="Hola",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[word],
        )
        result = TranscriptionResult(metadata=metadata, segments=[segment])
        assert result.metadata == metadata
        assert len(result.segments) == 1
        assert result.segments[0].text == "Hola"

    def test_transcription_result_empty_segments(self):
        """TranscriptionResult with empty segments is valid (silent audio)."""
        metadata = Metadata(
            file="silent.mp3",
            file_size_bytes=500,
            duration_seconds=5.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=2.0,
            created_at="2026-01-01T00:00:00Z",
        )
        result = TranscriptionResult(metadata=metadata, segments=[])
        assert result.segments == []

    def test_to_dict_produces_dict(self):
        """to_dict() returns a dictionary."""
        metadata = Metadata(
            file="test.mp3",
            file_size_bytes=1000,
            duration_seconds=10.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=5.0,
            created_at="2026-01-01T00:00:00Z",
        )
        word = Word(word="Hola", start=0.0, end=0.4, confidence=0.92)
        segment = Segment(
            id=0,
            start=0.0,
            end=0.4,
            text="Hola",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[word],
        )
        result = TranscriptionResult(metadata=metadata, segments=[segment])
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "metadata" in d
        assert "segments" in d

    def test_to_dict_serializable(self):
        """to_dict() produces JSON-serializable output."""
        metadata = Metadata(
            file="test.mp3",
            file_size_bytes=1000,
            duration_seconds=10.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=5.0,
            created_at="2026-01-01T00:00:00Z",
        )
        word = Word(word="Hola", start=0.0, end=0.4, confidence=0.92)
        segment = Segment(
            id=0,
            start=0.0,
            end=0.4,
            text="Hola",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[word],
        )
        result = TranscriptionResult(metadata=metadata, segments=[segment])
        d = result.to_dict()
        # Should not raise
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_to_dict_confidence_field(self):
        """to_dict() includes confidence field in words."""
        metadata = Metadata(
            file="test.mp3",
            file_size_bytes=1000,
            duration_seconds=10.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=5.0,
            created_at="2026-01-01T00:00:00Z",
        )
        word = Word(word="Hola", start=0.0, end=0.4, confidence=0.92)
        segment = Segment(
            id=0,
            start=0.0,
            end=0.4,
            text="Hola",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[word],
        )
        result = TranscriptionResult(metadata=metadata, segments=[segment])
        d = result.to_dict()
        assert d["segments"][0]["words"][0]["confidence"] == 0.92

    def test_to_json_produces_string(self):
        """to_json() returns a JSON string."""
        metadata = Metadata(
            file="test.mp3",
            file_size_bytes=1000,
            duration_seconds=10.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=5.0,
            created_at="2026-01-01T00:00:00Z",
        )
        word = Word(word="Hola", start=0.0, end=0.4, confidence=0.92)
        segment = Segment(
            id=0,
            start=0.0,
            end=0.4,
            text="Hola",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[word],
        )
        result = TranscriptionResult(metadata=metadata, segments=[segment])
        json_str = result.to_json()
        assert isinstance(json_str, str)
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_to_json_with_indent(self):
        """to_json(indent=2) produces formatted JSON."""
        metadata = Metadata(
            file="test.mp3",
            file_size_bytes=1000,
            duration_seconds=10.0,
            language="es",
            model="mlx-community/whisper-large-v3-turbo",
            transcription_time_seconds=5.0,
            created_at="2026-01-01T00:00:00Z",
        )
        result = TranscriptionResult(metadata=metadata, segments=[])
        json_str = result.to_json(indent=2)
        # Should contain newlines and spaces (formatted)
        assert "\n" in json_str
        assert "  " in json_str
