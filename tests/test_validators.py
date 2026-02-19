"""Tests for audio validators module (TDD: RED → GREEN → REFACTOR)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from whisper_meetings.validators import (
    check_ffmpeg_installed,
    validate_audio_file,
    get_audio_duration,
    get_audio_file_size,
    AudioFileInfo,
    InvalidAudioError,
    EXIT_OK,
    EXIT_ERROR,
    EXIT_FILE_NOT_FOUND,
    EXIT_FFMPEG_MISSING,
    EXIT_INVALID_AUDIO,
)


class TestExitCodeConstants:
    """Verify exit code constants have the correct values."""

    def test_exit_ok_is_zero(self):
        assert EXIT_OK == 0

    def test_exit_error_is_one(self):
        assert EXIT_ERROR == 1

    def test_exit_file_not_found_is_two(self):
        assert EXIT_FILE_NOT_FOUND == 2

    def test_exit_ffmpeg_missing_is_three(self):
        assert EXIT_FFMPEG_MISSING == 3

    def test_exit_invalid_audio_is_four(self):
        assert EXIT_INVALID_AUDIO == 4


class TestCheckFfmpegInstalled:
    """Tests for check_ffmpeg_installed()."""

    def test_check_ffmpeg_installed_found(self, mocker):
        """ffmpeg exists in PATH → returns True."""
        mock_result = MagicMock(returncode=0)
        mock_run = mocker.patch(
            "whisper_meetings.validators.subprocess.run",
            return_value=mock_result,
        )

        result = check_ffmpeg_installed()

        assert result is True
        mock_run.assert_called_once_with(["ffmpeg", "-version"], capture_output=True)

    def test_check_ffmpeg_installed_missing(self, mocker):
        """ffmpeg not in PATH → returns False."""
        mocker.patch(
            "whisper_meetings.validators.subprocess.run",
            side_effect=FileNotFoundError,
        )

        result = check_ffmpeg_installed()

        assert result is False


class TestValidateAudioFile:
    """Tests for validate_audio_file()."""

    def test_validate_audio_file_exists(self, tmp_path, mocker):
        """File exists and has audio stream → returns AudioFileInfo."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio content")

        # Three subprocess.run calls:
        # 1. ffprobe audio stream check → "audio\n"
        # 2. ffprobe duration (inside get_audio_duration) → "3600.5\n"
        # 3. ffprobe format name → "mp3\n"
        mock_calls = [
            MagicMock(returncode=0, stdout="audio\n"),
            MagicMock(returncode=0, stdout="3600.5\n"),
            MagicMock(returncode=0, stdout="mp3\n"),
        ]
        mocker.patch(
            "whisper_meetings.validators.subprocess.run",
            side_effect=mock_calls,
        )

        result = validate_audio_file(str(audio_file))

        assert isinstance(result, AudioFileInfo)
        assert result.path == str(audio_file)
        assert result.file_size_bytes == len(b"fake audio content")
        assert result.duration_seconds == 3600.5
        assert result.format_name == "mp3"

    def test_validate_audio_file_not_found(self, tmp_path):
        """File doesn't exist → raises FileNotFoundError."""
        missing_file = tmp_path / "nonexistent.mp3"

        with pytest.raises(FileNotFoundError):
            validate_audio_file(str(missing_file))

    def test_validate_audio_file_zero_bytes(self, tmp_path):
        """File is empty (0 bytes) → raises InvalidAudioError."""
        empty_file = tmp_path / "empty.mp3"
        empty_file.write_bytes(b"")  # zero bytes, no subprocess needed

        with pytest.raises(InvalidAudioError):
            validate_audio_file(str(empty_file))

    def test_validate_audio_file_no_audio_stream(self, tmp_path, mocker):
        """File has no audio stream → raises InvalidAudioError."""
        no_audio = tmp_path / "no_audio.mp4"
        no_audio.write_bytes(b"fake video without audio stream")

        # ffprobe returns empty string → no audio stream present
        mocker.patch(
            "whisper_meetings.validators.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=""),
        )

        with pytest.raises(InvalidAudioError):
            validate_audio_file(str(no_audio))


class TestGetAudioDuration:
    """Tests for get_audio_duration()."""

    def test_get_audio_duration(self, tmp_path, mocker):
        """Returns audio duration in seconds as a float."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_result = MagicMock(returncode=0, stdout="3600.5\n")
        mock_run = mocker.patch(
            "whisper_meetings.validators.subprocess.run",
            return_value=mock_result,
        )

        duration = get_audio_duration(str(audio_file))

        assert duration == 3600.5
        assert isinstance(duration, float)
        # Verify correct ffprobe command was used
        mock_run.assert_called_once_with(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(audio_file),
            ],
            capture_output=True,
            text=True,
        )


class TestGetAudioFileSize:
    """Tests for get_audio_file_size()."""

    def test_get_audio_file_size(self, tmp_path):
        """Returns file size in bytes as an integer (no subprocess needed)."""
        audio_file = tmp_path / "test.mp3"
        content = b"fake audio content 1234"
        audio_file.write_bytes(content)

        size = get_audio_file_size(str(audio_file))

        assert size == len(content)
        assert isinstance(size, int)
