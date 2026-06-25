from __future__ import annotations

from dataclasses import dataclass

from rag_core.text import HEADING_RE, normalize_whitespace


@dataclass(frozen=True)
class TextSection:
    title: str | None
    heading: str | None
    line_start: int
    line_end: int
    text: str


def split_markdown_sections(text: str) -> list[TextSection]:
    lines = text.splitlines()
    sections: list[TextSection] = []
    current_start = 1
    current_heading: str | None = None
    title: str | None = None

    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if not match:
            continue

        heading = match.group(2).strip()
        if title is None and match.group(1) == "#":
            title = heading

        if index > current_start:
            chunk_text = "\n".join(lines[current_start - 1 : index - 1]).strip()
            if chunk_text:
                sections.append(
                    TextSection(
                        title=title,
                        heading=current_heading,
                        line_start=current_start,
                        line_end=index - 1,
                        text=chunk_text,
                    )
                )
        current_start = index
        current_heading = heading

    tail = "\n".join(lines[current_start - 1 :]).strip()
    if tail:
        sections.append(
            TextSection(
                title=title,
                heading=current_heading,
                line_start=current_start,
                line_end=max(current_start, len(lines)),
                text=tail,
            )
        )

    if sections:
        return sections

    stripped = text.strip()
    if not stripped:
        return []
    return [
        TextSection(
            title=None,
            heading=None,
            line_start=1,
            line_end=max(1, len(lines)),
            text=stripped,
        )
    ]


def split_large_section(section: TextSection, max_chars: int) -> list[TextSection]:
    if len(section.text) <= max_chars:
        return [section]

    paragraphs = [part.strip() for part in section.text.split("\n\n") if part.strip()]
    chunks: list[TextSection] = []
    current: list[str] = []
    current_len = 0
    line_cursor = section.line_start

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if current and current_len + paragraph_len + 2 > max_chars:
            joined = "\n\n".join(current)
            line_count = joined.count("\n") + 1
            chunks.append(
                TextSection(
                    title=section.title,
                    heading=section.heading,
                    line_start=line_cursor,
                    line_end=line_cursor + line_count - 1,
                    text=joined,
                )
            )
            line_cursor += line_count
            current = []
            current_len = 0

        if paragraph_len > max_chars:
            for start in range(0, paragraph_len, max_chars):
                part = paragraph[start : start + max_chars]
                chunks.append(
                    TextSection(
                        title=section.title,
                        heading=section.heading,
                        line_start=line_cursor,
                        line_end=line_cursor + part.count("\n"),
                        text=part,
                    )
                )
                line_cursor += part.count("\n") + 1
            continue

        current.append(paragraph)
        current_len += paragraph_len + 2

    if current:
        joined = "\n\n".join(current)
        chunks.append(
            TextSection(
                title=section.title,
                heading=section.heading,
                line_start=line_cursor,
                line_end=min(section.line_end, line_cursor + joined.count("\n")),
                text=joined,
            )
        )

    return [chunk for chunk in chunks if normalize_whitespace(chunk.text)]

