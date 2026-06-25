from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from rag_core.collections import DEFAULT_COLLECTIONS, CollectionSpec, iter_collection_files
from rag_core.markdown import split_large_section, split_markdown_sections
from rag_core.models import RagChunk, RagIndexManifest, RagSource, SourceFileRecord
from rag_core.text import read_text, slugify


INDEX_FILE = "chunks.jsonl"
MANIFEST_FILE = "manifest.json"


def make_chunk_id(collection: str, relative_path: str, line_start: int, text: str) -> str:
    digest = hashlib.sha1(f"{collection}:{relative_path}:{line_start}:{text}".encode("utf-8")).hexdigest()
    return f"{collection}:{slugify(relative_path)}:{line_start}:{digest[:10]}"


def chunks_for_file(
    project_root: Path,
    collection: str,
    path: Path,
    max_chars: int = 1800,
) -> list[RagChunk]:
    text = read_text(path)
    relative_path = path.relative_to(project_root).as_posix()
    sections = split_markdown_sections(text)
    chunks: list[RagChunk] = []

    for section in sections:
        for small_section in split_large_section(section, max_chars=max_chars):
            chunk_text = small_section.text.strip()
            if not chunk_text:
                continue
            source = RagSource(
                collection=collection,
                path=relative_path,
                title=small_section.title,
                heading=small_section.heading,
                line_start=small_section.line_start,
                line_end=max(small_section.line_start, small_section.line_end),
            )
            chunks.append(
                RagChunk(
                    id=make_chunk_id(collection, relative_path, small_section.line_start, chunk_text),
                    collection=collection,
                    source=source,
                    text=chunk_text,
                    char_count=len(chunk_text),
                    metadata={"source_extension": path.suffix.lower()},
                )
            )

    return chunks


def build_index(
    project_root: Path,
    index_dir: Path,
    collections: tuple[CollectionSpec, ...] = DEFAULT_COLLECTIONS,
    max_chars: int = 1800,
) -> RagIndexManifest:
    project_root = project_root.resolve()
    index_dir = (project_root / index_dir).resolve() if not index_dir.is_absolute() else index_dir.resolve()
    index_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: list[RagChunk] = []
    source_records: list[SourceFileRecord] = []

    for spec in collections:
        for path in iter_collection_files(project_root, spec):
            chunks = chunks_for_file(project_root, spec.name, path, max_chars=max_chars)
            if not chunks:
                continue
            all_chunks.extend(chunks)
            source_records.append(
                SourceFileRecord(
                    collection=spec.name,
                    path=path.relative_to(project_root).as_posix(),
                    chunks=len(chunks),
                    char_count=sum(chunk.char_count for chunk in chunks),
                )
            )

    chunks_path = index_dir / INDEX_FILE
    with chunks_path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in all_chunks:
            handle.write(chunk.model_dump_json(ensure_ascii=False))
            handle.write("\n")

    manifest = RagIndexManifest(
        built_at=datetime.now(timezone.utc),
        project_root=project_root.as_posix(),
        chunk_count=len(all_chunks),
        source_files=source_records,
        collections={spec.name: spec.description for spec in collections},
    )
    (index_dir / MANIFEST_FILE).write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def load_chunks(index_dir: Path) -> list[RagChunk]:
    chunks_path = index_dir / INDEX_FILE
    if not chunks_path.exists():
        raise FileNotFoundError(f"RAG index not found: {chunks_path}")

    chunks: list[RagChunk] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                chunks.append(RagChunk.model_validate_json(line))
    return chunks

