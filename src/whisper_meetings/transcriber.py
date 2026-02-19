"""Transcription service — orchestrates the full audio-to-JSON pipeline."""

import time

import mlx_whisper

from whisper_meetings.mapper import map_transcription
from whisper_meetings.validators import check_ffmpeg_installed, validate_audio_file
from whisper_meetings.schema import TranscriptionResult

MODEL_REPO = "mlx-community/whisper-large-v3-mlx"
LANGUAGE = "es"


class FFmpegNotFoundError(Exception):
    """Raised when ffmpeg is not installed or not found in PATH."""


class Transcriber:
    """Orchestrates the full audio-to-TranscriptionResult pipeline.

    Orchestration order:
        1. check_ffmpeg_installed()  → FFmpegNotFoundError if missing
        2. validate_audio_file()     → AudioFileInfo or raise
        3. start timer               → time.perf_counter()
        4. mlx_whisper.transcribe()  → with word_timestamps=True
           fallback: retry without word_timestamps on TypeError
        5. measure elapsed           → time.perf_counter() - start
        6. map_transcription()       → TranscriptionResult
        7. return result
    """

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe an audio file to a structured TranscriptionResult.

        Args:
            audio_path: Path to the audio file to transcribe.

        Returns:
            TranscriptionResult with metadata, segments, and word-level data.

        Raises:
            FFmpegNotFoundError: If ffmpeg is not installed or not in PATH.
            FileNotFoundError: If the audio file does not exist.
            InvalidAudioError: If the file is not a valid audio file.
        """
        # Step 1: Verify ffmpeg is available (fail fast before any file I/O)
        if not check_ffmpeg_installed():
            raise FFmpegNotFoundError(
                "ffmpeg is not installed or not found in PATH. "
                "Install it with: brew install ffmpeg"
            )

        # Step 2: Validate audio file and gather metadata
        info = validate_audio_file(audio_path)

        # Step 3: Start wall-clock timer
        start = time.perf_counter()

        # Step 4: Run mlx_whisper with word_timestamps; fallback on TypeError
        try:
            raw = mlx_whisper.transcribe(
                audio_path,
                path_or_hf_repo=MODEL_REPO,
                language=LANGUAGE,
                word_timestamps=True,
                verbose=False,
            )
        except TypeError:
            raw = mlx_whisper.transcribe(
                audio_path,
                path_or_hf_repo=MODEL_REPO,
                language=LANGUAGE,
                verbose=False,
            )

        # Step 5: Measure elapsed transcription time
        elapsed = time.perf_counter() - start

        # Steps 6 & 7: Map raw output to domain schema and return
        return map_transcription(
            raw,
            audio_path,
            info.file_size_bytes,
            info.duration_seconds,
            elapsed,
        )
