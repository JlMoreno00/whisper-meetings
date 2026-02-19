"""Schema mapper: converts raw mlx-whisper output to TranscriptionResult."""

from datetime import datetime, timezone

from whisper_meetings.schema import Metadata, Segment, TranscriptionResult, Word

MODEL = "mlx-community/whisper-large-v3-mlx"
DEFAULT_LANGUAGE = "es"


def map_transcription(
    raw_result: dict,
    file_path: str,
    file_size_bytes: int,
    duration_seconds: float,
    transcription_time_seconds: float,
) -> TranscriptionResult:
    """Map raw mlx_whisper.transcribe() output to a TranscriptionResult.

    Args:
        raw_result: Direct return value of mlx_whisper.transcribe().
        file_path: Path (or name) of the source audio file.
        file_size_bytes: Size of the source audio file in bytes.
        duration_seconds: Duration of the audio in seconds.
        transcription_time_seconds: Wall-clock time spent transcribing.

    Returns:
        TranscriptionResult with all fields populated.
    """
    language = raw_result.get("language") or DEFAULT_LANGUAGE

    metadata = Metadata(
        file=file_path,
        file_size_bytes=file_size_bytes,
        duration_seconds=duration_seconds,
        language=language,
        model=MODEL,
        transcription_time_seconds=transcription_time_seconds,
        created_at=_utc_now_iso(),
    )

    segments = [_map_segment(seg) for seg in raw_result.get("segments", [])]

    return TranscriptionResult(metadata=metadata, segments=segments)


def _map_segment(raw_seg: dict) -> Segment:
    raw_words = raw_seg.get("words", [])
    words = [_map_word(w) for w in raw_words]

    return Segment(
        id=raw_seg["id"],
        start=raw_seg["start"],
        end=raw_seg["end"],
        text=raw_seg["text"],
        avg_logprob=raw_seg["avg_logprob"],
        no_speech_prob=raw_seg["no_speech_prob"],
        words=words,
    )


def _map_word(raw_word: dict) -> Word:
    # mlx-whisper uses "probability"; our schema field is "confidence"
    return Word(
        word=raw_word["word"],
        start=raw_word["start"],
        end=raw_word["end"],
        confidence=raw_word["probability"],
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
