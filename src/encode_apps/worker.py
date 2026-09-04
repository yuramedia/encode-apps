"""Background QThread worker that runs the ffmpeg encode process."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from encode_apps.encoder import (
    EncodeSettings,
    MarathonEncodeSettings,
    MarathonEpisodeItem,
    ProbeResult,
    build_ffmpeg_command,
    build_marathon_ffmpeg_command,
    probe_video,
)
from encode_apps.queue import QueueItem
from encode_apps.srt2ass import convert as srt2ass_convert

import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _RESOURCES = Path(sys._MEIPASS) / "encode_apps" / "resources"
else:
    _RESOURCES = Path(__file__).resolve().parent / "resources"

_DEFAULT_TEMPLATE = _RESOURCES / "Ani-One_ID_-_Template.ass"

# Regex to parse ffmpeg progress line
_PROGRESS_RE = re.compile(
    r"frame=\s*(?P<frame>\d+)\s+"
    r"fps=\s*(?P<fps>[\d.]+)\s+"
    r".*?"
    r"time=\s*(?P<time>[\d:.]+)\s+"
    r".*?"
    r"speed=\s*(?P<speed>\S+)"
)


class EncodeWorker(QThread):
    """Runs the full encode pipeline in a background thread.

    Signals
    -------
    log(str)
        Informational log line.
    progress(str)
        Real-time ffmpeg status (frame / fps / time / speed).
    finished(bool, str)
        ``(success, message)`` when work completes.
    """

    log = Signal(str)
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        audio_path: str = "",
        endcard_path: str = "",
        template_path: str = "",
        style: str | None = None,
        endcard_seconds: int = 10,
        video_bitrate: str = "",
        audio_bitrate: str = "",
        preset: str = "slow",
        parent=None,
    ):
        super().__init__(parent)
        self.video_path = video_path
        self.subtitle_path = subtitle_path
        self.output_path = output_path
        self.audio_path = audio_path
        self.endcard_path = endcard_path
        self.template_path = template_path
        self.style = style
        self.endcard_seconds = endcard_seconds
        self.video_bitrate = video_bitrate
        self.audio_bitrate = audio_bitrate
        self.preset = preset

        self._process: subprocess.Popen | None = None
        self._cancelled = False

    # ------------------------------------------------------------------
    def cancel(self) -> None:
        """Request cancellation — kills the running ffmpeg process."""
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.kill()

    # ------------------------------------------------------------------
    def run(self) -> None:  # noqa: C901 — long but linear pipeline
        temp_dir = tempfile.mkdtemp(prefix="encode_apps_")
        try:
            self._do_run(temp_dir)
        except Exception as exc:
            if not self._cancelled:
                self.finished.emit(False, str(exc))
        finally:
            # Clean up temp dir
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def _do_run(self, temp_dir: str) -> None:
        sub_ext = Path(self.subtitle_path).suffix.lower()
        ass_path = os.path.join(temp_dir, "subs.ass")

        # ── Step 1: prepare ASS ──────────────────────────────────────
        if sub_ext == ".ass":
            self.log.emit("Menyalin file ASS ke folder temp…")
            shutil.copy2(self.subtitle_path, ass_path)
        elif sub_ext == ".srt":
            tpl = self.template_path or str(_DEFAULT_TEMPLATE)
            if not tpl or not Path(tpl).is_file():
                self.finished.emit(False, "Template ASS diperlukan untuk konversi SRT.")
                return
            self.log.emit("Mengonversi SRT → ASS…")
            try:
                count, style_name = srt2ass_convert(
                    self.subtitle_path,
                    tpl,
                    ass_path,
                    self.style if self.style else None,
                )
                self.log.emit(
                    f"  wrote {ass_path} ({count} lines, base style: {style_name})"
                )
            except Exception as exc:
                self.finished.emit(False, f"Konversi SRT gagal: {exc}")
                return
        else:
            self.finished.emit(False, f"Format subtitle tidak didukung: {sub_ext}")
            return

        if self._cancelled:
            self.finished.emit(False, "Dibatalkan.")
            return

        # ── Step 2: probe video ──────────────────────────────────────
        self.log.emit("Menganalisis video sumber…")
        probe = probe_video(self.video_path)
        self.log.emit(
            f"  Resolusi: {probe.width}x{probe.height}, FPS: {probe.fps}, "
            f"Video Bitrate: {probe.video_bitrate or 'N/A'}, "
            f"Audio: {probe.audio_codec} {probe.audio_bitrate or 'N/A'}, "
            f"Profile: {probe.video_profile} L{probe.video_level}"
        )
        if self.audio_path:
            self.log.emit(f"  Dubbing audio: {Path(self.audio_path).name}")

        # ── Step 3: build & run ffmpeg ───────────────────────────────
        settings = EncodeSettings(
            video_path=self.video_path,
            ass_path=ass_path,
            output_path=self.output_path,
            audio_path=self.audio_path,
            endcard_path=self.endcard_path,
            endcard_seconds=self.endcard_seconds,
            video_bitrate=self.video_bitrate,
            audio_bitrate=self.audio_bitrate,
            preset=self.preset,
            probe=probe,
        )
        cmd = build_ffmpeg_command(settings)
        self.log.emit(f"Meng-encode 1-pass dengan ffmpeg (preset: {self.preset})…")

        # We chdir into temp_dir so ffmpeg's ass= filter finds subs.ass
        self._process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            cwd=temp_dir,
        )

        # Read stderr line-by-line for progress
        assert self._process.stderr is not None
        buf = ""
        for chunk in iter(lambda: self._process.stderr.read(1), ""):
            if self._cancelled:
                break
            if chunk == "\r" or chunk == "\n":
                line = buf.strip()
                if line:
                    m = _PROGRESS_RE.search(line)
                    if m:
                        self.progress.emit(
                            f"frame={m.group('frame')}  fps={m.group('fps')}  "
                            f"time={m.group('time')}  speed={m.group('speed')}"
                        )
                    elif line:
                        self.log.emit(f"  [ffmpeg] {line}")
                buf = ""
            else:
                buf += chunk

        self._process.wait()

        if self._cancelled:
            self.finished.emit(False, "Encoding dibatalkan oleh pengguna.")
            return

        rc = self._process.returncode
        if rc != 0:
            self.finished.emit(False, f"ffmpeg gagal (exit code {rc}).")
        else:
            self.finished.emit(True, f"Selesai: {self.output_path}")


class FullEpisodeWorker(QThread):
    """Worker that compiles multiple episode queue items into a single continuous video."""

    log = Signal(str)
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(
        self,
        queue_items: list[QueueItem],
        output_path: str,
        endcard_path: str = "",
        endcard_seconds: int = 10,
        video_bitrate: str = "",
        audio_bitrate: str = "",
        preset: str = "slow",
        parent=None,
    ):
        super().__init__(parent)
        self.queue_items = queue_items
        self.output_path = output_path
        self.endcard_path = endcard_path
        self.endcard_seconds = endcard_seconds
        self.video_bitrate = video_bitrate
        self.audio_bitrate = audio_bitrate
        self.preset = preset

        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.kill()

    def run(self) -> None:
        temp_dir = tempfile.mkdtemp(prefix="encode_apps_marathon_")
        try:
            self._do_run(temp_dir)
        except Exception as exc:
            if not self._cancelled:
                self.finished.emit(False, str(exc))
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def _do_run(self, temp_dir: str) -> None:
        if not self.queue_items:
            self.finished.emit(False, "Tidak ada job episode untuk dikompilasi.")
            return

        marathon_episodes: list[MarathonEpisodeItem] = []
        primary_probe = None

        self.log.emit(f"Memulai kompilasi Full Episode ({len(self.queue_items)} episode)…")

        for idx, item in enumerate(self.queue_items):
            if self._cancelled:
                self.finished.emit(False, "Full Episode encoding dibatalkan.")
                return

            sub_ext = Path(item.subtitle_path).suffix.lower()
            ass_path = os.path.join(temp_dir, f"subs_{idx}.ass")

            if sub_ext == ".ass":
                self.log.emit(f"  [{idx + 1}/{len(self.queue_items)}] Menyiapkan ASS untuk {Path(item.video_path).name}…")
                shutil.copy2(item.subtitle_path, ass_path)
            elif sub_ext == ".srt":
                tpl = item.template_path or str(_DEFAULT_TEMPLATE)
                if not tpl or not Path(tpl).is_file():
                    self.finished.emit(False, f"Template ASS tidak ditemukan untuk {item.subtitle_path}")
                    return
                self.log.emit(f"  [{idx + 1}/{len(self.queue_items)}] Mengonversi SRT → ASS untuk {Path(item.video_path).name}…")
                try:
                    count, style_name = srt2ass_convert(
                        item.subtitle_path,
                        tpl,
                        ass_path,
                        item.style if item.style else None,
                    )
                except Exception as exc:
                    self.finished.emit(False, f"Konversi SRT gagal: {exc}")
                    return

            probe = probe_video(item.video_path)
            if primary_probe is None:
                primary_probe = probe

            if item.audio_path:
                self.log.emit(f"    (Dubbing audio: {Path(item.audio_path).name})")

            marathon_episodes.append(
                MarathonEpisodeItem(
                    video_path=item.video_path,
                    ass_path=ass_path,
                    audio_path=item.audio_path,
                )
            )

        if self._cancelled:
            self.finished.emit(False, "Full Episode encoding dibatalkan.")
            return

        settings = MarathonEncodeSettings(
            episodes=marathon_episodes,
            output_path=self.output_path,
            endcard_path=self.endcard_path,
            endcard_seconds=self.endcard_seconds,
            video_bitrate=self.video_bitrate,
            audio_bitrate=self.audio_bitrate,
            preset=self.preset,
            probe=primary_probe or ProbeResult(),
        )

        cmd = build_marathon_ffmpeg_command(settings)
        self.log.emit("Meng-encode Full Episode (Marathon) dengan ffmpeg…")

        self._process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            cwd=temp_dir,
        )

        assert self._process.stderr is not None
        buf = ""
        for chunk in iter(lambda: self._process.stderr.read(1), ""):
            if self._cancelled:
                break
            if chunk == "\r" or chunk == "\n":
                line = buf.strip()
                if line:
                    m = _PROGRESS_RE.search(line)
                    if m:
                        self.progress.emit(
                            f"frame={m.group('frame')}  fps={m.group('fps')}  "
                            f"time={m.group('time')}  speed={m.group('speed')}"
                        )
                    elif line:
                        self.log.emit(f"  [ffmpeg] {line}")
                buf = ""
            else:
                buf += chunk

        self._process.wait()

        if self._cancelled:
            self.finished.emit(False, "Encoding dibatalkan oleh pengguna.")
            return

        rc = self._process.returncode
        if rc != 0:
            self.finished.emit(False, f"ffmpeg gagal (exit code {rc}).")
        else:
            self.finished.emit(True, f"Selesai Full Episode: {self.output_path}")

