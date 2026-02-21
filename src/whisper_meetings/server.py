from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import wave

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from whisper_meetings.streaming import (
    SAMPLE_RATE,
    SegmentTask,
    VADSegmenter,
    title_from_text,
    transcribe_pcm_bytes,
    warmup_transcriber,
)

MAX_PARTIAL_BACKLOG = 3


async def send_json(connection: ServerConnection, payload: dict[str, Any]) -> None:
    await connection.send(json.dumps(payload, ensure_ascii=False))


def now_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


async def transcription_worker(
    connection: ServerConnection,
    queue: asyncio.Queue[SegmentTask | None],
    finalized_messages: list[dict[str, Any]],
    title_state: dict[str, str],
) -> None:
    while True:
        task = await queue.get()
        if task is None:
            queue.task_done()
            break

        try:
            if task.kind == "partial" and queue.qsize() > 0:
                continue
            text = await asyncio.to_thread(transcribe_pcm_bytes, task.pcm_bytes)
            if not text:
                continue

            if task.kind == "partial":
                await send_json(
                    connection,
                    {
                        "type": "transcript.partial",
                        "text": text,
                        "segment_id": task.segment_id,
                    },
                )
            else:
                timestamp = now_hhmm()
                speaker = "Locutor"
                await send_json(
                    connection,
                    {
                        "type": "transcript.final",
                        "text": text,
                        "speaker": speaker,
                        "timestamp": timestamp,
                        "segment_id": task.segment_id,
                    },
                )
                finalized_messages.append(
                    {
                        "segment_id": task.segment_id,
                        "timestamp": timestamp,
                        "speaker": speaker,
                        "text": text,
                    }
                )
                title = title_from_text(text)
                if title:
                    title_state["title"] = title
                    await send_json(
                        connection,
                        {
                            "type": "title.update",
                            "title": title,
                        },
                    )
        except ConnectionClosed:
            break
        except Exception as exc:  # noqa: BLE001
            print(f"transcription error: {exc}", file=sys.stderr)
            try:
                await send_json(connection, {"type": "error", "message": str(exc)})
            except ConnectionClosed:
                break
        finally:
            queue.task_done()


def output_base_dir() -> Path:
    configured = os.environ.get("WHISPER_MEETINGS_OUTPUT_DIR")
    if configured:
        return Path(configured)
    return Path.home() / "Documents" / "WhisperMeetings"


def persist_session(
    started_at: datetime,
    audio_pcm: bytes,
    finalized_messages: list[dict[str, Any]],
    title: str,
) -> dict[str, str]:
    session_dir = output_base_dir() / started_at.strftime("%Y%m%d-%H%M%S")
    session_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = session_dir / "transcript.json"
    audio_path = session_dir / "audio.wav"

    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_pcm)

    payload = {
        "meeting_title": title,
        "created_at": started_at.isoformat(),
        "sample_rate": SAMPLE_RATE,
        "audio_file": str(audio_path),
        "transcript": finalized_messages,
    }
    transcript_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "session_dir": str(session_dir),
        "audio_path": str(audio_path),
        "transcript_path": str(transcript_path),
    }


async def handle_connection(connection: ServerConnection) -> None:
    segmenter = VADSegmenter()
    queue: asyncio.Queue[SegmentTask | None] = asyncio.Queue()
    finalized_messages: list[dict[str, Any]] = []
    title_state: dict[str, str] = {"title": ""}
    worker = asyncio.create_task(
        transcription_worker(connection, queue, finalized_messages, title_state)
    )
    session_audio = bytearray()
    session_started_at: datetime | None = None

    session_started = False

    try:
        async for message in connection:
            if isinstance(message, bytes):
                if not session_started:
                    await send_json(
                        connection,
                        {
                            "type": "error",
                            "message": "Audio received before session.start",
                        },
                    )
                    continue

                try:
                    tasks = segmenter.push_frame(message)
                except ValueError as exc:
                    await send_json(
                        connection,
                        {
                            "type": "error",
                            "message": str(exc),
                        },
                    )
                    continue

                session_audio.extend(message)

                has_final = any(task.kind == "final" for task in tasks)
                for task in tasks:
                    if has_final and task.kind == "partial":
                        continue
                    if task.kind == "partial" and queue.qsize() >= MAX_PARTIAL_BACKLOG:
                        continue
                    await queue.put(task)

                continue

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await send_json(
                    connection,
                    {
                        "type": "error",
                        "message": "Invalid JSON control message",
                    },
                )
                continue

            event_type = data.get("type")

            if event_type == "session.start":
                segmenter.reset()
                finalized_messages.clear()
                title_state["title"] = ""
                session_audio = bytearray()
                session_started_at = datetime.now()
                session_started = True
                await send_json(connection, {"type": "session.ready"})
                continue

            if event_type == "session.stop":
                for task in segmenter.flush():
                    await queue.put(task)
                await queue.join()
                if session_started_at is not None:
                    saved = await asyncio.to_thread(
                        persist_session,
                        session_started_at,
                        bytes(session_audio),
                        list(finalized_messages),
                        title_state.get("title", ""),
                    )
                    await send_json(
                        connection,
                        {
                            "type": "session.saved",
                            **saved,
                        },
                    )
                session_started = False
                continue

            await send_json(
                connection,
                {
                    "type": "error",
                    "message": f"Unsupported control message type: {event_type}",
                },
            )
    except ConnectionClosed:
        pass
    finally:
        if session_started:
            for task in segmenter.flush():
                await queue.put(task)
            await queue.join()
            if session_started_at is not None:
                try:
                    saved = await asyncio.to_thread(
                        persist_session,
                        session_started_at,
                        bytes(session_audio),
                        list(finalized_messages),
                        title_state.get("title", ""),
                    )
                    await send_json(connection, {"type": "session.saved", **saved})
                except ConnectionClosed:
                    pass

        await queue.put(None)
        await worker


async def run_server() -> None:
    port = int(os.environ.get("WS_PORT", "8766"))
    async with serve(handle_connection, "127.0.0.1", port):
        print(f"whisper-meetings websocket server listening on ws://127.0.0.1:{port}")
        asyncio.create_task(asyncio.to_thread(warmup_transcriber))
        await asyncio.Future()


def main() -> None:
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("server stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
