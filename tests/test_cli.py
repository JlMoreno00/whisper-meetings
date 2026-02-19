"""Tests for CLI entry point (Task 6)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from whisper_meetings.cli import main
from whisper_meetings.transcriber import FFmpegNotFoundError
from whisper_meetings.validators import InvalidAudioError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_result(
    json_content: str = '{"metadata": {}, "segments": []}',
    transcription_time_seconds: float = 3.7,
) -> MagicMock:
    """Return a mock TranscriptionResult whose to_json() returns *json_content*."""
    mock = MagicMock()
    mock.to_json.return_value = json_content
    mock.metadata.transcription_time_seconds = transcription_time_seconds
    return mock


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------


class TestCliHelp:
    def test_cli_help(self):
        """--help shows AUDIO_FILE, --output, --stdout, --word-timestamps, and description."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "AUDIO_FILE" in result.output
        assert "--output" in result.output
        assert "--stdout" in result.output
        assert "--word-timestamps" in result.output
        assert "Transcribe meeting audio" in result.output


# ---------------------------------------------------------------------------
# Happy-path scenarios
# ---------------------------------------------------------------------------


class TestCliTranscribeSuccess:
    def test_cli_transcribe_file_success(self, tmp_path, mocker):
        """Valid audio file → writes JSON to default path → exit code 0."""
        mock_result = make_mock_result()
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.return_value = mock_result

        audio_file = tmp_path / "meeting.mp3"

        runner = CliRunner()
        result = runner.invoke(main, [str(audio_file)])

        assert result.exit_code == 0
        expected_output = tmp_path / "meeting.json"
        assert expected_output.exists()
        assert json.loads(expected_output.read_text()) == {
            "metadata": {},
            "segments": [],
        }

    def test_cli_transcribe_stdout(self, tmp_path, mocker):
        """--stdout → JSON on stdout only, status messages on stderr → exit code 0."""
        json_content = '{"metadata": {}, "segments": []}'
        mock_result = make_mock_result(json_content)
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.return_value = mock_result

        audio_file = tmp_path / "meeting.mp3"

        runner = CliRunner()
        result = runner.invoke(main, [str(audio_file), "--stdout"])

        assert result.exit_code == 0
        # JSON must appear on stdout only; status messages go to stderr
        assert json.loads(result.stdout) == {"metadata": {}, "segments": []}
        assert "Transcrib" not in result.stdout

    def test_cli_transcribe_with_output(self, tmp_path, mocker):
        """--output custom.json → writes JSON to specified path → exit code 0."""
        mock_result = make_mock_result()
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.return_value = mock_result

        audio_file = tmp_path / "meeting.mp3"
        custom_output = tmp_path / "custom.json"

        runner = CliRunner()
        result = runner.invoke(main, [str(audio_file), "--output", str(custom_output)])

        assert result.exit_code == 0
        assert custom_output.exists()
        assert json.loads(custom_output.read_text()) == {"metadata": {}, "segments": []}

    def test_cli_default_output_name(self, tmp_path, mocker):
        """meeting.mp3 → generates meeting.json in same directory."""
        mock_result = make_mock_result()
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.return_value = mock_result

        audio_file = tmp_path / "meeting.mp3"
        expected_output = tmp_path / "meeting.json"

        runner = CliRunner()
        result = runner.invoke(main, [str(audio_file)])

        assert result.exit_code == 0
        assert expected_output.exists()

    def test_cli_completion_message_includes_time(self, tmp_path, mocker):
        """Success path → stderr contains 'Transcription completed in X.Xs'."""
        mock_result = make_mock_result(transcription_time_seconds=5.3)
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.return_value = mock_result

        audio_file = tmp_path / "meeting.mp3"

        runner = CliRunner()
        result = runner.invoke(main, [str(audio_file)])

        assert result.exit_code == 0
        assert "Transcription completed in 5.3s" in result.stderr

    def test_cli_overwrites_existing(self, tmp_path, mocker):
        """If output file already exists, it is overwritten without prompting."""
        new_json = '{"metadata": {"new": true}, "segments": []}'
        mock_result = make_mock_result(new_json)
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.return_value = mock_result

        audio_file = tmp_path / "meeting.mp3"
        expected_output = tmp_path / "meeting.json"
        # Pre-populate the output file with stale content
        expected_output.write_text('{"old": "content"}')

        runner = CliRunner()
        result = runner.invoke(main, [str(audio_file)])

        assert result.exit_code == 0
        content = json.loads(expected_output.read_text())
        # Old key must be gone; new content must be present
        assert "old" not in content
        assert "metadata" in content


# ---------------------------------------------------------------------------
# Error-handling / exit codes
# ---------------------------------------------------------------------------


class TestCliErrors:
    def test_cli_file_not_found(self, mocker):
        """Missing file → stderr with 'not found' message → exit code 2."""
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.side_effect = FileNotFoundError(
            "File '/nonexistent/file.mp3' not found."
        )

        runner = CliRunner()
        result = runner.invoke(main, ["/nonexistent/file.mp3"])

        assert result.exit_code == 2
        assert "not found" in result.stderr.lower()

    def test_cli_ffmpeg_missing(self, mocker):
        """ffmpeg absent → stderr with install hint → exit code 3."""
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.side_effect = FFmpegNotFoundError(
            "ffmpeg not installed"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["/some/audio.mp3"])

        assert result.exit_code == 3
        assert "ffmpeg" in result.stderr.lower()
        assert "brew install ffmpeg" in result.stderr

    def test_cli_invalid_audio(self, mocker):
        """Invalid audio file → stderr with message → exit code 4."""
        mock_transcriber = mocker.patch("whisper_meetings.cli.Transcriber")
        mock_transcriber.return_value.transcribe.side_effect = InvalidAudioError(
            "No audio stream detected"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["/some/audio.mp3"])

        assert result.exit_code == 4
        assert (
            "not a valid audio file" in result.stderr
            or "audio" in result.stderr.lower()
        )
