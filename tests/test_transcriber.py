"""Tests for the Transcriber service — Task 5 (TDD: RED → GREEN → REFACTOR)."""

import pytest

from whisper_meetings.transcriber import (
    FFmpegNotFoundError,
    LANGUAGE,
    MODEL_REPO,
    Transcriber,
)
from whisper_meetings.validators import AudioFileInfo, InvalidAudioError
from whisper_meetings.schema import TranscriptionResult

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MOCK_AUDIO_INFO = AudioFileInfo(
    path="test.mp3",
    file_size_bytes=15_000,
    duration_seconds=10.0,
    format_name="mp3",
)

MOCK_MLX_OUTPUT = {
    "text": "Hola mundo",
    "segments": [
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 1.0,
            "text": "Hola mundo",
            "tokens": [],
            "temperature": 0.0,
            "avg_logprob": -0.2,
            "compression_ratio": 1.0,
            "no_speech_prob": 0.01,
            "words": [
                {"word": "Hola", "start": 0.0, "end": 0.5, "probability": 0.95},
                {"word": "mundo", "start": 0.5, "end": 1.0, "probability": 0.92},
            ],
        }
    ],
    "language": "es",
}

MOCK_MLX_OUTPUT_NO_WORDS = {
    "text": "Hola mundo",
    "segments": [
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 1.0,
            "text": "Hola mundo",
            "tokens": [],
            "temperature": 0.0,
            "avg_logprob": -0.2,
            "compression_ratio": 1.0,
            "no_speech_prob": 0.01,
            # no "words" key — simulates word_timestamps=False output
        }
    ],
    "language": "es",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTranscriber:
    def test_transcribe_happy_path(self, mocker):
        """Valid file + ffmpeg present → complete TranscriptionResult."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed", return_value=True
        )
        mocker.patch(
            "whisper_meetings.transcriber.validate_audio_file",
            return_value=MOCK_AUDIO_INFO,
        )
        mocker.patch(
            "whisper_meetings.transcriber.mlx_whisper.transcribe",
            return_value=MOCK_MLX_OUTPUT,
        )

        result = Transcriber().transcribe("test.mp3")

        assert isinstance(result, TranscriptionResult)
        assert result.metadata.file == "test.mp3"
        assert result.metadata.language == "es"
        assert result.metadata.model == MODEL_REPO
        assert len(result.segments) == 1
        assert len(result.segments[0].words) == 2
        assert result.segments[0].words[0].confidence == pytest.approx(0.95)

    def test_transcribe_file_not_found(self, mocker):
        """Non-existent file → FileNotFoundError propagated from validator."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed", return_value=True
        )
        mocker.patch(
            "whisper_meetings.transcriber.validate_audio_file",
            side_effect=FileNotFoundError("File 'ghost.mp3' not found."),
        )

        with pytest.raises(FileNotFoundError):
            Transcriber().transcribe("ghost.mp3")

    def test_transcribe_ffmpeg_missing(self, mocker):
        """ffmpeg not installed → FFmpegNotFoundError raised before touching the file."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed", return_value=False
        )

        with pytest.raises(FFmpegNotFoundError):
            Transcriber().transcribe("test.mp3")

    def test_transcribe_invalid_audio(self, mocker):
        """File with no audio stream → InvalidAudioError propagated from validator."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed", return_value=True
        )
        mocker.patch(
            "whisper_meetings.transcriber.validate_audio_file",
            side_effect=InvalidAudioError("No audio stream."),
        )

        with pytest.raises(InvalidAudioError):
            Transcriber().transcribe("silent.mp3")

    def test_transcribe_calls_mlx_with_correct_params(self, mocker):
        """mlx_whisper.transcribe is called with the exact required parameters."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed", return_value=True
        )
        mocker.patch(
            "whisper_meetings.transcriber.validate_audio_file",
            return_value=MOCK_AUDIO_INFO,
        )
        mock_transcribe = mocker.patch(
            "whisper_meetings.transcriber.mlx_whisper.transcribe",
            return_value=MOCK_MLX_OUTPUT,
        )

        Transcriber().transcribe("test.mp3")

        mock_transcribe.assert_called_once_with(
            "test.mp3",
            path_or_hf_repo=MODEL_REPO,
            language=LANGUAGE,
            word_timestamps=True,
            verbose=False,
        )

    def test_transcribe_measures_time(self, mocker):
        """transcription_time_seconds reflects actual wall-clock time spent in mlx_whisper."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed", return_value=True
        )
        mocker.patch(
            "whisper_meetings.transcriber.validate_audio_file",
            return_value=MOCK_AUDIO_INFO,
        )
        mocker.patch(
            "whisper_meetings.transcriber.mlx_whisper.transcribe",
            return_value=MOCK_MLX_OUTPUT,
        )
        # Simulate start=0.0, end=2.5 → elapsed=2.5
        mocker.patch(
            "whisper_meetings.transcriber.time.perf_counter",
            side_effect=[0.0, 2.5],
        )

        result = Transcriber().transcribe("test.mp3")

        assert result.metadata.transcription_time_seconds == pytest.approx(2.5)

    def test_transcribe_word_timestamps_fallback(self, mocker):
        """If mlx_whisper raises TypeError on word_timestamps, retry without it."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed", return_value=True
        )
        mocker.patch(
            "whisper_meetings.transcriber.validate_audio_file",
            return_value=MOCK_AUDIO_INFO,
        )
        mock_transcribe = mocker.patch(
            "whisper_meetings.transcriber.mlx_whisper.transcribe"
        )
        mock_transcribe.side_effect = [
            TypeError("unexpected keyword argument 'word_timestamps'"),
            MOCK_MLX_OUTPUT_NO_WORDS,
        ]

        result = Transcriber().transcribe("test.mp3")

        # Called twice: first with word_timestamps, then without
        assert mock_transcribe.call_count == 2

        first_kwargs = mock_transcribe.call_args_list[0].kwargs
        assert first_kwargs.get("word_timestamps") is True

        second_kwargs = mock_transcribe.call_args_list[1].kwargs
        assert "word_timestamps" not in second_kwargs

        # Result is still a valid TranscriptionResult (words will be empty)
        assert isinstance(result, TranscriptionResult)
        assert result.segments[0].words == []


# ---------------------------------------------------------------------------
# Module-level constant tests
# ---------------------------------------------------------------------------


def test_model_repo_constant():
    assert MODEL_REPO == "mlx-community/whisper-large-v3-mlx"


def test_language_constant():
    assert LANGUAGE == "es"
