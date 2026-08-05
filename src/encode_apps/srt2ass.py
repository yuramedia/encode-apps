"""SRT → ASS conversion using styles from a template .ass file.

Ported from the standalone ``srt2ass.py`` script.
"""

from __future__ import annotations

import re
from pathlib import Path

import pysubs2

FULL_ITALIC_RE = re.compile(r"^\{\\i1\}(.*)\{\\i0\}$", re.DOTALL)


def pick_default_style(template: pysubs2.SSAFile) -> str:
    """Return the first style that isn't Italics / Top / Typesettings."""
    for name in template.styles:
        low = name.lower()
        if "italic" not in low and "top" not in low and "typesetting" not in low:
            return name
    return next(iter(template.styles))


def get_available_styles(template_path: str | Path) -> list[str]:
    """Return all style names from a template .ass file."""
    template = pysubs2.load(str(template_path))
    return list(template.styles.keys())


def convert(
    srt_path: str | Path,
    template_path: str | Path,
    output_path: str | Path,
    style: str | None = None,
) -> tuple[int, str]:
    """Convert *srt_path* to ASS at *output_path* using styles from *template_path*.

    Returns ``(line_count, base_style_name)``.
    """
    template = pysubs2.load(str(template_path))
    subs = pysubs2.load(str(srt_path))

    subs.info = template.info
    subs.styles = template.styles

    base_style = style or pick_default_style(template)
    if base_style not in template.styles:
        available = list(template.styles.keys())
        raise ValueError(
            f"Style '{base_style}' not found in template. Available: {available}"
        )

    italics_candidate = f"{base_style} Italics"
    italics_style = italics_candidate if italics_candidate in template.styles else None

    for line in subs:
        line.style = base_style
        match = FULL_ITALIC_RE.match(line.text)
        if match and italics_style:
            line.text = match.group(1)
            line.style = italics_style

    subs.save(str(output_path))
    return len(subs), base_style
