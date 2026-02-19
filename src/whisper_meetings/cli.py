"""CLI entry point for whisper-meetings."""

import click


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
    pass


if __name__ == "__main__":
    main()
