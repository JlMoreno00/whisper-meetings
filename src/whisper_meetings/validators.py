import subprocess
from dataclasses import dataclass
from pathlib import Path

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_FFMPEG_MISSING = 3
EXIT_INVALID_AUDIO = 4


class InvalidAudioError(Exception):
    pass


@dataclass
class AudioFileInfo:
    path: str
    file_size_bytes: int
    duration_seconds: float
    format_name: str


def check_ffmpeg_installed() -> bool:
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def validate_audio_file(path: str) -> AudioFileInfo:
    """Raises FileNotFoundError if missing, InvalidAudioError if empty or no audio stream."""
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File '{path}' not found.")

    file_size = file_path.stat().st_size
    if file_size == 0:
        raise InvalidAudioError(f"File '{path}' is empty (0 bytes).")

    stream_result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if not stream_result.stdout.strip():
        raise InvalidAudioError(f"File '{path}' has no audio stream.")

    duration = get_audio_duration(path)

    fmt_result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=format_name",
            "-of",
            "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
    )
    format_name = fmt_result.stdout.strip()

    return AudioFileInfo(
        path=path,
        file_size_bytes=file_size,
        duration_seconds=duration,
        format_name=format_name,
    )


def get_audio_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def get_audio_file_size(path: str) -> int:
    return Path(path).stat().st_size
