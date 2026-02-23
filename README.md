# Nøva

Local-first meeting transcription powered by [mlx-whisper](https://github.com/ml-explore/mlx-examples)
on Apple Silicon. No cloud, no subscriptions, no data leaves your machine.

The project has three interfaces that share the same Python backend:

| Interface | Description |
|---|---|
| **CLI** | Transcribe audio files to structured JSON |
| **Electron app** | Real-time desktop app with 3D audio visualization |
| **Demo page** | Standalone HTML demo with mock data (no backend required) |

## Requirements

- **Python 3.10+**
- **Apple Silicon Mac** (M1 / M2 / M3 / M4) — mlx-whisper runs on the Apple Neural Engine
- **ffmpeg** — required by mlx-whisper for audio decoding
- **Node.js 18+** — only needed for the Electron app
- **[uv](https://docs.astral.sh/uv/)** — Python package manager

```bash
brew install ffmpeg
```

## Quick start

```bash
# 1. Clone and install Python dependencies
git clone https://github.com/JlMoreno00/whisper-meetings.git
cd whisper-meetings
uv sync

# 2. Transcribe a file (CLI)
uv run whisper-meetings meeting.mp3

# 3. Or launch the desktop app
cd electron && npm install && npm start
```

The first run downloads the model (`mlx-community/whisper-large-v3-turbo`, ~3 GB) from
Hugging Face and caches it locally. Subsequent runs are fast.

## CLI usage

```
whisper-meetings AUDIO_FILE [--output/-o PATH] [--stdout] [--word-timestamps]
```

| Option | Description |
|---|---|
| `AUDIO_FILE` | Path to the audio file (MP3, WAV, M4A, FLAC, OGG, WebM) |
| `--output`, `-o` | Write JSON to this path (default: `<audio_name>.json`) |
| `--stdout` | Print JSON to stdout; status messages go to stderr |
| `--word-timestamps` | Include per-word timestamps and confidence scores (slower) |

### Examples

```bash
# Basic — output saved next to the source file
whisper-meetings meeting.mp3

# Custom output path
whisper-meetings recording.m4a -o transcripts/2026-02-19.json

# Pipe to jq
whisper-meetings standup.mp3 --stdout | jq '.metadata.duration_seconds'
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Unexpected error |
| `2` | Audio file not found |
| `3` | ffmpeg not installed or not in PATH |
| `4` | File is not a valid audio file |

## Electron app

The desktop app streams microphone audio to a local WebSocket server, transcribes in
real time with VAD (Voice Activity Detection), and displays results alongside a reactive
3D particle sphere.

```bash
cd electron
npm install
npm start        # production mode
npm run dev      # opens DevTools
```

The app automatically starts the Python WebSocket backend and reconnects if it drops.
When you stop a recording the full session (audio WAV + transcript JSON) is saved to
`~/Documents/WhisperMeetings/<timestamp>/`.

### Features

- Real-time transcription with partial (interim) results
- Auto-generated meeting title from transcript content
- 3D particle sphere that reacts to microphone audio (Three.js)
- Multiple visual themes and a control panel for particle size, opacity, glow, backgrounds, color palettes, and custom presets
- Session persistence — audio and transcript saved automatically
- Drag-and-drop file transcription

## WebSocket server

The streaming backend can also run standalone for custom integrations:

```bash
uv run python -m whisper_meetings.server
```

Default port is `8766` (override with `WS_PORT` env var). The server binds to
`127.0.0.1` (loopback only).

### Protocol

The WebSocket protocol uses JSON control messages and raw binary PCM frames:

**Client to server:**

| Message | Format | Description |
|---|---|---|
| `session.start` | JSON `{"type": "session.start"}` | Begin a new recording session |
| Audio frames | Binary (640 bytes) | 16-bit PCM, 16 kHz mono, 20 ms frames |
| `session.stop` | JSON `{"type": "session.stop"}` | End the session and persist |

**Server to client:**

| Message | Description |
|---|---|
| `session.ready` | Session initialized, ready for audio |
| `transcript.partial` | Interim transcription (may change) |
| `transcript.final` | Finalized segment with timestamp and speaker |
| `title.update` | Auto-generated meeting title |
| `session.saved` | Session persisted to disk (includes paths) |
| `error` | Error message |

## Demo page

A standalone HTML page that showcases the 3D visualization with mock transcript data.
No backend required — open `demo/index.html` in a browser.

## Privacy

Everything runs locally on your machine:

- The Whisper model runs on-device via Apple's MLX framework
- Audio is processed in-memory and never sent to any external service
- The WebSocket server binds to `127.0.0.1` (loopback) — not accessible from the network
- Saved sessions stay on your local filesystem

## License

[MIT](LICENSE)
