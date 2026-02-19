"""JSON output schema dataclasses for transcription results."""

import json
from dataclasses import dataclass, asdict


@dataclass
class Word:
    """Represents a single word in a transcription segment."""

    word: str
    start: float
    end: float
    confidence: float


@dataclass
class Segment:
    """Represents a segment of transcription with multiple words."""

    id: int
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    words: list[Word]


@dataclass
class Metadata:
    """Metadata about the transcription and source audio."""

    file: str
    file_size_bytes: int
    duration_seconds: float
    language: str
    model: str
    transcription_time_seconds: float
    created_at: str  # ISO 8601 format


@dataclass
class TranscriptionResult:
    """Complete transcription result with metadata and segments."""

    metadata: Metadata
    segments: list[Segment]

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary.

        Returns:
            dict: Dictionary representation with all nested objects converted.
        """
        return {
            "metadata": asdict(self.metadata),
            "segments": [
                {
                    "id": seg.id,
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "avg_logprob": seg.avg_logprob,
                    "no_speech_prob": seg.no_speech_prob,
                    "words": [asdict(w) for w in seg.words],
                }
                for seg in self.segments
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to a JSON string.

        Args:
            indent: Number of spaces for indentation. Defaults to 2.

        Returns:
            str: JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=indent)
