"""Batch / Queue encoding data models and helper functions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".ts", ".m2ts"}
SUBTITLE_EXTENSIONS = {".srt", ".ass"}
AUDIO_EXTENSIONS = {".mp3", ".aac", ".m4a", ".wav", ".flac", ".opus", ".ogg"}


@dataclass
class QueueItem:
    """Represents a single encoding job in the queue."""

    video_path: str
    subtitle_path: str
    output_path: str
    audio_path: str = ""
    endcard_path: str = ""
    template_path: str = ""
    style: str | None = None
    endcard_seconds: int = 10
    video_bitrate: str = ""
    audio_bitrate: str = ""
    preset: str = "slow"
    status: str = "Pending"  # Pending, Encoding, Completed, Failed, Cancelled
    progress_text: str = ""
    error_msg: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


def auto_pair_files(
    file_paths: list[str | Path],
) -> list[tuple[Path, Path | None, Path | None]]:
    """Scan file paths and pair videos with subtitles and dubbing audio sharing the same stem."""
    paths = [Path(p) for p in file_paths]
    videos: list[Path] = []
    subtitles: dict[str, Path] = {}
    audios: dict[str, Path] = {}

    for p in paths:
        ext = p.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            videos.append(p)
        elif ext in SUBTITLE_EXTENSIONS:
            subtitles[p.stem.lower()] = p
        elif ext in AUDIO_EXTENSIONS:
            audios[p.stem.lower()] = p

    pairs: list[tuple[Path, Path | None, Path | None]] = []
    for v in videos:
        sub = subtitles.get(v.stem.lower())
        aud = audios.get(v.stem.lower())
        pairs.append((v, sub, aud))

    return pairs

