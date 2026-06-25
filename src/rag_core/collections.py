from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    root: Path
    extensions: tuple[str, ...]
    description: str
    exclude_dirs: tuple[str, ...] = field(
        default=(".git", ".venv", "__pycache__", ".pytest_cache", "output")
    )


DEFAULT_COLLECTIONS: tuple[CollectionSpec, ...] = (
    CollectionSpec(
        name="project_docs",
        root=Path("project_docs"),
        extensions=(".md", ".markdown"),
        description="Architecture, roadmap, decisions, and current project state.",
    ),
    CollectionSpec(
        name="methodology_notes",
        root=Path("methodology_notes"),
        extensions=(".md", ".markdown"),
        description="Methods, tools, and domain notes for extraction and chemistry work.",
    ),
    CollectionSpec(
        name="code_examples",
        root=Path("code_examples"),
        extensions=(".md", ".markdown", ".py"),
        description="Reusable code patterns and extraction examples.",
    ),
    CollectionSpec(
        name="molecule_facts",
        root=Path("molecule_facts"),
        extensions=(".md", ".markdown", ".csv", ".json"),
        description="Factual molecule records and source datasets.",
    ),
)


def iter_collection_files(project_root: Path, spec: CollectionSpec) -> list[Path]:
    collection_root = project_root / spec.root
    if not collection_root.exists():
        return []

    files: list[Path] = []
    for path in collection_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in spec.exclude_dirs for part in path.relative_to(collection_root).parts):
            continue
        if path.suffix.lower() in spec.extensions:
            files.append(path)
    return sorted(files)

