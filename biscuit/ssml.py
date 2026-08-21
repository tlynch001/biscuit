"""SSML helpers for ElevenLabs Multilingual v2 performance scripts.

Only ``<break time="Ns" />`` is used. Spoken words are never altered.
"""

from __future__ import annotations

import re

_BREAK_TAG = re.compile(r"<break\s+time=\"([0-9.]+)s\"\s*/>", re.IGNORECASE)
_OTHER_TAGS = re.compile(r"</?speak>", re.IGNORECASE)


def ssml_break(seconds: float) -> str:
    """Return an ElevenLabs-compatible break tag, or empty if no pause."""

    if seconds <= 0:
        return ""
    value = f"{seconds:.2f}".rstrip("0").rstrip(".")
    return f'<break time="{value}s" />'


def strip_ssml(text: str) -> str:
    """Remove break/speak tags, leaving spoken words and paragraph breaks."""

    without_breaks = _BREAK_TAG.sub(" ", text)
    without_tags = _OTHER_TAGS.sub(" ", without_breaks)
    paragraphs = [" ".join(block.split()) for block in without_tags.split("\n\n")]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def spoken_fingerprint(text: str) -> str:
    """Collapse whitespace for comparing spoken copy without touching words."""

    return " ".join(strip_ssml(text).split())
