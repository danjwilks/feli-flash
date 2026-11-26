"""Markdown-to-HTML rendering and deterministic Anki ID helpers."""

from __future__ import annotations

import hashlib
import re

import markdown

# Preserve Anki cloze tags {{c1::...}} so Markdown syntax never mangles them.
_CLOZE_TOKEN_RE = re.compile(r"(\{\{c\d+::.*?\}\})", re.DOTALL)


def stable_int_id(namespace: str, key: str) -> int:
    """Generate a deterministic 31-bit integer ID in Anki's safe range [1<<30, 1<<31)."""
    digest = hashlib.sha256(f"{namespace}:{key}".encode("utf-8")).digest()
    raw = int.from_bytes(digest[:4], "big")
    return (1 << 30) + (raw % ((1 << 30) - 1))


def render_markdown(text: str, *, preserve_cloze: bool = False) -> str:
    """Render Markdown text to clean HTML suitable for Anki card fields."""
    if not text:
        return ""

    placeholders: dict[str, str] = {}
    working = text

    if preserve_cloze:
        def _stash(match: re.Match[str]) -> str:
            token = f"ZZFELICLOZE{len(placeholders)}ZZ"
            placeholders[token] = match.group(1)
            return token

        working = _CLOZE_TOKEN_RE.sub(_stash, working)

    html = markdown.markdown(
        working,
        extensions=["extra", "nl2br", "sane_lists"],
        output_format="html",
    ).strip()

    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]

    if preserve_cloze and placeholders:
        for token, original in placeholders.items():
            html = html.replace(token, original)

    return html
