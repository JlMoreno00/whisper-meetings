"""Integration tests — end-to-end pipeline via CliRunner with boundary mocks.

Mocking strategy:
  - mlx_whisper.transcribe: ML model boundary (avoids real 3GB model download)
  - check_ffmpeg_installed: system subprocess boundary
  - validate_audio_file: file system + ffprobe boundary

The full pipeline runs: CLI -> Transcriber -> mapper -> schema -> JSON output.
"""

import json

import pytest
from click.testing import CliRunner

from whisper_meetings.cli import main


# ---------------------------------------------------------------------------
# Happy-path scenarios
# ---------------------------------------------------------------------------


class TestFullPipelineHappyPath:
    def test_full_pipeline_happy_path(
        self,
        mock_mlx_whisper,
        mock_ffmpeg_installed,
        mock_validate_audio,
        sample_audio_path,
    ):
        """Full pipeline: boundary mocks -> CLI -> JSON file written -> exit code 0.

        Verifies the complete data flow: CLI invocation -> Transcriber ->
        mapper (probability -> confidence) -> schema -> JSON file on disk.
        """
        runner = CliRunner()
        result = runner.invoke(main, [str(sample_audio_path)])

        assert result.exit_code == 0

        expected_output = sample_audio_path.with_suffix(".json")
        assert expected_output.exists(), "Output JSON file was not created"

        data = json.loads(expected_output.read_text())

        # Top-level shape
        assert "metadata" in data
        assert "segments" in data

        # Segment and word content from the mock mlx output
        assert len(data["segments"]) == 1
        words = data["segments"][0]["words"]
        assert len(words) == 6

        # Mapper must rename probability -> confidence
        assert "confidence" in words[0]
        assert "probability" not in words[0]
        assert words[0]["confidence"] == pytest.approx(0.92)

    def test_full_pipeline_stdout_mode(
        self,
        mock_mlx_whisper,
        mock_ffmpeg_installed,
        mock_validate_audio,
        sample_audio_path,
    ):
        """--stdout mode: JSON on stdout, status messages on stderr -> exit code 0."""
        runner = CliRunner()
        result = runner.invoke(main, [str(sample_audio_path), "--stdout"])

        assert result.exit_code == 0

        # stdout should contain valid JSON only
        data = json.loads(result.stdout)
        assert "metadata" in data
        assert "segments" in data

        # Status messages must NOT appear in stdout
        assert "Transcrib" not in result.stdout

        # Status messages appear in stderr
        assert "Transcrib" in result.stderr or "complete" in result.stderr.lower()

    def test_full_pipeline_output_flag(
        self,
        mock_mlx_whisper,
        mock_ffmpeg_installed,
        mock_validate_audio,
        sample_audio_path,
        tmp_path,
    ):
        """--output path: JSON written to specified path -> exit code 0."""
        custom_output = tmp_path / "custom_output.json"

        runner = CliRunner()
        result = runner.invoke(
            main, [str(sample_audio_path), "--output", str(custom_output)]
        )

        assert result.exit_code == 0
        assert custom_output.exists(), "Custom output path was not created"

        data = json.loads(custom_output.read_text())
        assert "metadata" in data
        assert "segments" in data


# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------


class TestFullPipelineErrors:
    def test_full_pipeline_error_file_not_found(self, mocker):
        """Non-existent audio file -> stderr message -> exit code 2."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed",
            return_value=True,
        )
        mocker.patch(
            "whisper_meetings.transcriber.validate_audio_file",
            side_effect=FileNotFoundError("File '/nonexistent/audio.mp3' not found."),
        )

        runner = CliRunner()
        result = runner.invoke(main, ["/nonexistent/audio.mp3"])

        assert result.exit_code == 2
        assert "not found" in result.stderr.lower()

    def test_full_pipeline_error_ffmpeg_missing(self, mocker):
        """ffmpeg not available -> stderr with install hint -> exit code 3."""
        mocker.patch(
            "whisper_meetings.transcriber.check_ffmpeg_installed",
            return_value=False,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["/some/audio.mp3"])

        assert result.exit_code == 3
        assert "ffmpeg" in result.stderr.lower()
        assert "brew install ffmpeg" in result.stderr


# ---------------------------------------------------------------------------
# JSON schema shape validation
# ---------------------------------------------------------------------------


class TestFullPipelineSchemaValidation:
    def test_full_pipeline_json_schema_valid(
        self,
        mock_mlx_whisper,
        mock_ffmpeg_installed,
        mock_validate_audio,
        sample_audio_path,
    ):
        """Output JSON matches exact schema: all required fields with correct types."""
        runner = CliRunner()
        result = runner.invoke(main, [str(sample_audio_path), "--stdout"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)

        # --- metadata ---
        meta = data["metadata"]
        assert isinstance(meta["file"], str)
        assert isinstance(meta["file_size_bytes"], int)
        assert isinstance(meta["duration_seconds"], float)
        assert isinstance(meta["language"], str)
        assert isinstance(meta["model"], str)
        assert isinstance(meta["transcription_time_seconds"], float)
        assert isinstance(meta["created_at"], str)

        # Values from mock / pipeline constants
        assert meta["language"] == "es"
        assert meta["model"] == "mlx-community/whisper-large-v3-turbo"
        assert meta["file_size_bytes"] == 15_234_567
        assert meta["duration_seconds"] == pytest.approx(3600.5)

        # created_at should look like an ISO 8601 timestamp
        assert "T" in meta["created_at"] and "Z" in meta["created_at"]

        # --- segments ---
        assert isinstance(data["segments"], list)
        seg = data["segments"][0]
        assert isinstance(seg["id"], int)
        assert isinstance(seg["start"], float)
        assert isinstance(seg["end"], float)
        assert isinstance(seg["text"], str)
        assert isinstance(seg["avg_logprob"], float)
        assert isinstance(seg["no_speech_prob"], float)
        assert isinstance(seg["words"], list)

        # --- words ---
        word = seg["words"][0]
        assert isinstance(word["word"], str)
        assert isinstance(word["start"], float)
        assert isinstance(word["end"], float)
        assert isinstance(word["confidence"], float)
        assert "probability" not in word, "probability must be renamed to confidence"
