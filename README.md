# whisper-meetings

CLI tool that transcribes meeting audio files to structured JSON using
[mlx-whisper](https://github.com/ml-explore/mlx-examples) (Whisper large-v3) running
locally on Apple Silicon. No cloud, no subscriptions — everything stays on your machine.

Phase 1 covers the core pipeline: audio file in, JSON transcript out. The output includes
per-word timestamps and confidence scores, making it ready for downstream summarisation,
search, or speaker diarisation (planned for Phase 2).

## Requirements

- **Python 3.10+**
- **Apple Silicon Mac** (M1/M2/M3) — mlx-whisper is optimised for the Apple Neural Engine
- **ffmpeg** — required by mlx-whisper for audio decoding

Install ffmpeg with Homebrew if you don't have it:

```bash
brew install ffmpeg
```

## Installation

```bash
# Clone the repository and install all dependencies with uv
uv sync
```

The first time you run a transcription the model (`mlx-community/whisper-large-v3-turbo`,
roughly 3 GB) will be downloaded automatically from Hugging Face and cached locally.
Subsequent runs are fast.

## Usage

```
whisper-meetings AUDIO_FILE [--output/-o PATH] [--stdout]
```

| Argument / Option | Description |
|---|---|
| `AUDIO_FILE` | Path to the audio file (MP3, WAV, M4A, FLAC, OGG, WebM) |
| `--output`, `-o PATH` | Write JSON to this path instead of the default |
| `--stdout` | Print JSON to stdout; status messages go to stderr |

### Examples

**Basic usage** — output saved to `meeting.json` in the same directory:

```bash
whisper-meetings meeting.mp3
```

**Custom output path**:

```bash
whisper-meetings recording.m4a --output transcripts/2026-02-19.json
```

**Pipe JSON to another tool** (JSON on stdout, status on stderr):

```bash
whisper-meetings weekly-standup.mp3 --stdout | jq '.metadata.duration_seconds'
```

## JSON Output Schema

```json
{
  "metadata": {
    "file": "meeting.mp3",
    "file_size_bytes": 15234567,
    "duration_seconds": 3600.5,
    "language": "es",
    "model": "mlx-community/whisper-large-v3-turbo",
    "transcription_time_seconds": 245.3,
    "created_at": "2026-02-19T10:30:00Z"
  },
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 5.2,
      "text": "Hola, bienvenidos a la reunion semanal.",
      "avg_logprob": -0.234,
      "no_speech_prob": 0.012,
      "words": [
        {"word": "Hola,",       "start": 0.00, "end": 0.40, "confidence": 0.92},
        {"word": "bienvenidos", "start": 0.50, "end": 1.10, "confidence": 0.87}
      ]
    }
  ]
}
```

The `confidence` field on each word is sourced from mlx-whisper's internal `probability`
value (renamed for clarity).

## Exit Codes

| Exit code | Meaning |
|---|---|
| `0` | Transcription completed successfully |
| `1` | Unexpected error |
| `2` | Audio file not found |
| `3` | ffmpeg not installed or not in PATH |
| `4` | File is not a valid audio file (no audio stream) |

## Development

```bash
# Install dev dependencies
uv sync

# Run the full test suite
uv run pytest -v

# Run integration tests only
uv run pytest tests/test_integration.py -v
```

All tests are fully mocked — no real model download or audio processing occurs during
`uv run pytest`.
