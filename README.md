# encode-apps

Cross-platform GUI hardsub encoder — burn-in ASS/SRT subtitles with ffmpeg.

## Prerequisites

- Python 3.10+
- `uv` package manager
- `ffmpeg` and `ffprobe` in system PATH

## Installation

```bash
uv sync
```

## Running

```bash
uv run encode-apps
# or
uv run python -m encode_apps
```

## Building Executables

```bash
uv run pyinstaller --noconfirm --onefile --windowed --name encode-apps --add-data "src/encode_apps/resources/Ani-One_ID_-_Template.ass:encode_apps/resources" src/encode_apps/__main__.py
```

(Use `;` instead of `:` for path separator on Windows).
