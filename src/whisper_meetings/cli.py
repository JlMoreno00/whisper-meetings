"""CLI entry point for whisper-meetings."""

import sys
from pathlib import Path

import click

from .transcriber import FFmpegNotFoundError, Transcriber
from .validators import (
    EXIT_ERROR,
    EXIT_FILE_NOT_FOUND,
    EXIT_FFMPEG_MISSING,
    EXIT_INVALID_AUDIO,
    InvalidAudioError,
)


@click.command()
@click.argument("audio_file")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output JSON file path. Default: <audio_name>.json",
)
@click.option(
    "--stdout", "use_stdout", is_flag=True, help="Output JSON to stdout instead of file"
)
def main(audio_file: str, output: str | None, use_stdout: bool) -> None:
    """Transcribe meeting audio to structured JSON using Whisper."""
    # 1. Determine output path (only needed for file mode)
    output_path: Path | None = None
    if not use_stdout:
        output_path = (
            Path(output)
            if output is not None
            else Path(audio_file).with_suffix(".json")
        )

    # 2. Status: announce transcription start
    click.echo(f"Transcribing {audio_file}...", err=True)

    try:
        # 3. Run the pipeline (thin wrapper — all logic lives in Transcriber)
        result = Transcriber().transcribe(audio_file)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(EXIT_FILE_NOT_FOUND)
    except FFmpegNotFoundError:
        click.echo(
            "Error: ffmpeg not found. Install it with: brew install ffmpeg", err=True
        )
        sys.exit(EXIT_FFMPEG_MISSING)
    except InvalidAudioError:
        click.echo(
            f"Error: '{audio_file}' is not a valid audio file or has no audio stream.",
            err=True,
        )
        sys.exit(EXIT_INVALID_AUDIO)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(EXIT_ERROR)

    # 4. Status: transcription complete with elapsed time from result metadata
    elapsed = result.metadata.transcription_time_seconds
    click.echo(f"Transcription completed in {elapsed:.1f}s", err=True)

    # 5. Emit JSON output
    json_output = result.to_json(indent=2)

    if use_stdout:
        click.echo(json_output)
    else:
        assert output_path is not None  # guaranteed: set above when not use_stdout
        output_path.write_text(json_output, encoding="utf-8")
        click.echo(f"Output saved to {output_path}", err=True)


if __name__ == "__main__":
    main()
