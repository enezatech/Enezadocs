from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def chunk_markdown(body: str, max_chars: int = 1000, overlap: int = 200) -> list[dict]:
    """Split markdown into heading-aware, size-bounded chunks.

    Each chunk is a dict with ``ordinal``, ``heading`` and ``content``. Sections
    are delimited by markdown headings and then packed into pieces of at most
    ``max_chars`` characters with ``overlap`` characters of context carried over.
    """
    chunks: list[dict] = []
    ordinal = 0
    for heading, section in _sections(body):
        for piece in _split_size(section, max_chars, overlap):
            chunks.append({"ordinal": ordinal, "heading": heading, "content": piece})
            ordinal += 1
    return chunks


def _sections(body: str):
    sections: list[tuple[str, str]] = []
    heading = ""
    buffer: list[str] = []
    in_fence = False

    def flush():
        text = "\n".join(buffer).strip()
        if text:
            sections.append((heading, text))

    for line in (body or "").split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            buffer.append(line)
            continue
        match = None if in_fence else _HEADING_RE.match(line)
        if match:
            flush()
            heading = match.group(2).strip()
            buffer = [line]
        else:
            buffer.append(line)
    flush()
    return sections


def _split_size(text: str, max_chars: int, overlap: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            newline = text.rfind("\n", start, end)
            if newline > start + max_chars // 2:
                end = newline
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return pieces
