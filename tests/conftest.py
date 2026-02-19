"""Shared pytest fixtures for integration and unit tests."""

import pytest

from whisper_meetings.validators import AudioFileInfo


# ---------------------------------------------------------------------------
# Shared mock data (reusable across fixtures and test modules)
# ---------------------------------------------------------------------------

MOCK_MLX_RESULT = {
    "text": "Hola, bienvenidos a la reunión semanal.",
    "segments": [
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 5.2,
            "text": "Hola, bienvenidos a la reunión semanal.",
            "tokens": [50258, 12188, 11, 3228, 1456, 1660],
            "temperature": 0.0,
            "avg_logprob": -0.234,
            "compression_ratio": 1.45,
            "no_speech_prob": 0.012,
            "words": [
                {"word": "Hola,", "start": 0.0, "end": 0.4, "probability": 0.92},
                {"word": "bienvenidos", "start": 0.5, "end": 1.1, "probability": 0.87},
                {"word": "a", "start": 1.15, "end": 1.2, "probability": 0.95},
                {"word": "la", "start": 1.25, "end": 1.3, "probability": 0.96},
                {"word": "reunión", "start": 1.35, "end": 1.7, "probability": 0.89},
                {"word": "semanal.", "start": 1.75, "end": 2.1, "probability": 0.91},
            ],
        }
    ],
    "language": "es",
}

MOCK_AUDIO_INFO = AudioFileInfo(
    path="meeting.mp3",
    file_size_bytes=15_234_567,
    duration_seconds=3600.5,
    format_name="mp3",
)


# ---------------------------------------------------------------------------
# Integration-test fixtures — patch external boundaries only
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mlx_whisper(mocker):
    """Patch mlx_whisper.transcribe at the module boundary.

    Returns realistic raw output (uses 'probability', not 'confidence') to
    exercise the full mapper → schema pipeline.
    """
    return mocker.patch(
        "whisper_meetings.transcriber.mlx_whisper.transcribe",
        return_value=MOCK_MLX_RESULT,
    )


@pytest.fixture
def mock_ffmpeg_installed(mocker):
    """Patch check_ffmpeg_installed to simulate ffmpeg being present."""
    return mocker.patch(
        "whisper_meetings.transcriber.check_ffmpeg_installed",
        return_value=True,
    )


@pytest.fixture
def mock_validate_audio(mocker):
    """Patch validate_audio_file to skip real ffprobe I/O and return mock info."""
    return mocker.patch(
        "whisper_meetings.transcriber.validate_audio_file",
        return_value=MOCK_AUDIO_INFO,
    )


@pytest.fixture
def sample_audio_path(tmp_path):
    """Create a temporary file that acts as the audio input for CLI invocations."""
    audio = tmp_path / "meeting.mp3"
    audio.write_bytes(b"fake audio content - not real audio")
    return audio
