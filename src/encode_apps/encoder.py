"""FFmpeg / FFprobe wrapper — video probing and command building.

Replicates all encoding logic from ``encok-hardsub.ps1``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def check_dependencies() -> list[str]:
    """Return list of missing executables (empty = all OK)."""
    missing = []
    for cmd in ("ffmpeg", "ffprobe"):
        if shutil.which(cmd) is None:
            missing.append(cmd)
    return missing


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Metadata extracted from a video file via ``ffprobe``."""

    width: int = 0
    height: int = 0
    fps: str = "24000/1001"
    video_bitrate: str = ""
    video_profile: str = "main"
    video_level: str = "4.1"
    audio_codec: str = ""
    audio_bitrate: str = ""
    audio_sample_rate: str = "48000"
    audio_channels: str = "2"
    duration_seconds: float = 0.0


def normalize_profile(raw_profile: str) -> str:
    """Map ffprobe profile names to valid x264 -profile:v strings."""
    p = raw_profile.lower().strip()
    if "constrained baseline" in p or "baseline" in p:
        return "baseline"
    elif "main" in p:
        return "main"
    elif "high 10" in p or "high10" in p:
        return "high10"
    elif "high 4:2:2" in p or "high422" in p:
        return "high422"
    elif "high 4:4:4" in p or "high444" in p:
        return "high444"
    elif "high" in p:
        return "high"
    return "main"


def _run_probe(args: list[str]) -> str:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def probe_video(path: str | Path) -> ProbeResult:
    """Run ``ffprobe`` on *path* and return a :class:`ProbeResult`."""
    path = str(path)
    pr = ProbeResult()

    # Video stream info
    try:
        out = _run_probe([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,bit_rate,profile,level",
            "-of", "json", path,
        ])
        data = json.loads(out)
        stream = data.get("streams", [{}])[0]

        pr.width = int(stream.get("width", 0))
        pr.height = int(stream.get("height", 0))
        pr.fps = stream.get("r_frame_rate", "24000/1001")

        vbit = stream.get("bit_rate", "")
        if vbit and vbit != "N/A":
            pr.video_bitrate = vbit

        profile = stream.get("profile", "")
        if profile and profile != "N/A":
            pr.video_profile = normalize_profile(profile)

        level_raw = stream.get("level", "")
        if level_raw and str(level_raw) != "N/A":
            level_str = str(level_raw)
            try:
                level_num = int(level_str)
                if level_num <= 0:
                    pr.video_level = "4.1"
                elif len(level_str) == 2:
                    pr.video_level = f"{level_str[0]}.{level_str[1]}"
                else:
                    pr.video_level = level_str
            except ValueError:
                if "." in level_str and not level_str.startswith("-"):
                    pr.video_level = level_str
                else:
                    pr.video_level = "4.1"
    except Exception:
        pass

    # Fallback: video bitrate from format
    if not pr.video_bitrate:
        try:
            out = _run_probe([
                "ffprobe", "-v", "error",
                "-show_entries", "format=bit_rate",
                "-of", "json", path,
            ])
            data = json.loads(out)
            fbit = data.get("format", {}).get("bit_rate", "")
            if fbit and fbit != "N/A":
                pr.video_bitrate = fbit
        except Exception:
            pass

    # Audio stream info
    try:
        out = _run_probe([
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,bit_rate,sample_rate,channels",
            "-of", "json", path,
        ])
        data = json.loads(out)
        stream = data.get("streams", [{}])[0]

        pr.audio_codec = stream.get("codec_name", "").lower()

        abit = stream.get("bit_rate", "")
        if abit and abit != "N/A":
            pr.audio_bitrate = abit

        sr = stream.get("sample_rate", "")
        if sr and sr != "N/A":
            pr.audio_sample_rate = sr

        ch = stream.get("channels", "")
        if ch and str(ch) != "N/A":
            pr.audio_channels = str(ch)
    except Exception:
        pass

    # Duration
    try:
        out = _run_probe([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ])
        data = json.loads(out)
        dur = data.get("format", {}).get("duration", "0")
        pr.duration_seconds = float(dur)
    except Exception:
        pass

    return pr


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------

@dataclass
class EncodeSettings:
    """All parameters needed to build the ffmpeg command."""

    video_path: str = ""
    ass_path: str = ""             # path to subs.ass inside temp dir
    output_path: str = ""
    endcard_path: str = ""         # optional
    endcard_seconds: int = 10
    video_bitrate: str = ""        # auto-detect if empty
    audio_bitrate: str = ""        # auto-detect if empty
    preset: str = "slow"
    # Probed values (filled by caller)
    probe: ProbeResult = field(default_factory=ProbeResult)


def build_ffmpeg_command(s: EncodeSettings) -> list[str]:
    """Return the full ``ffmpeg`` argv list for encoding."""

    probe = s.probe

    # Resolve profile & bitrates
    v_profile = normalize_profile(probe.video_profile)
    v_bitrate = s.video_bitrate or probe.video_bitrate or "25400k"
    a_bitrate = s.audio_bitrate or probe.audio_bitrate or "320k"

    # x264 args
    x264 = [
        "-c:v", "libx264",
        "-profile:v", v_profile,
        "-level", probe.video_level,
        "-refs", "3", "-bf", "0",
        "-g", "30", "-keyint_min", "30",
        "-sc_threshold", "0", "-coder", "ac",
        "-x264-params", "me=umh:rc-lookahead=250:aq-mode=3:deblock=-1,-1:qcomp=0.60",
        "-preset", s.preset,
        "-b:v", v_bitrate,
    ]

    # ass filename (we chdir into the temp dir, so just the basename)
    ass_basename = Path(s.ass_path).name

    if s.endcard_path:
        w, h = probe.width or 1920, probe.height or 1080
        fps = probe.fps or "24000/1001"
        sr = probe.audio_sample_rate

        filter_complex = (
            f"[0:v]ass={ass_basename}[v0sub];"
            f"[v0sub]format=yuv420p[v0];"
            f"[1:v]fps={fps},scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p[v1];"
            f"[v0][0:a][v1][2:a]concat=n=2:v=1:a=1[outv][outa]"
        )
        inputs = [
            "-i", s.video_path,
            "-loop", "1", "-t", str(s.endcard_seconds), "-i", s.endcard_path,
            "-f", "lavfi", "-t", str(s.endcard_seconds),
            "-i", f"anullsrc=r={sr}:cl=stereo",
        ]
        mapping = ["-map", "[outv]", "-map", "[outa]"]
        audio_args = ["-c:a", "aac", "-b:a", a_bitrate,
                      "-ar", sr, "-ac", probe.audio_channels]
    else:
        filter_complex = f"[0:v]ass={ass_basename},format=yuv420p[outv]"
        inputs = ["-i", s.video_path]
        mapping = ["-map", "[outv]", "-map", "0:a"]

        if probe.audio_codec == "aac":
            audio_args = ["-c:a", "copy"]
        else:
            audio_args = ["-c:a", "aac", "-b:a", a_bitrate,
                          "-ar", probe.audio_sample_rate,
                          "-ac", probe.audio_channels]

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
        *inputs,
        "-filter_complex", filter_complex,
        *mapping,
        *x264,
        *audio_args,
        "-movflags", "+faststart", "-brand", "mp42",
        s.output_path,
    ]
    return cmd
