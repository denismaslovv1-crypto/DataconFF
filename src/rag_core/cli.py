from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rag_core.index import build_index
from rag_core.retriever import RagRetriever
from rag_core.vector_index import build_vector_index, query_vector_index


def build_command(args: argparse.Namespace) -> int:
    manifest = build_index(
        project_root=Path(args.root),
        index_dir=Path(args.index_dir),
        max_chars=args.max_chars,
    )
    print(f"Built RAG index: {manifest.chunk_count} chunks from {len(manifest.source_files)} files")
    print(f"Index directory: {Path(args.index_dir).as_posix()}")
    return 0


def query_command(args: argparse.Namespace) -> int:
    retriever = RagRetriever(Path(args.index_dir))
    results = retriever.search(args.query, top_k=args.top_k, collection=args.collection)
    for index, result in enumerate(results, start=1):
        source = result.chunk.source
        print(f"{index}. score={result.score} collection={source.collection}")
        print(f"   source={source.path}:{source.line_start}-{source.line_end}")
        if source.heading:
            print(f"   heading={source.heading}")
        print(f"   matched={', '.join(result.matched_terms)}")
        preview = result.chunk.text.replace("\n", " ")
        print(f"   {preview[: args.preview_chars]}")
    return 0


def vector_build_command(args: argparse.Namespace) -> int:
    count = build_vector_index(
        project_root=Path(args.root),
        index_dir=Path(args.index_dir),
        config_path=Path(args.config) if args.config else None,
        collection=args.collection,
        rebuild_text_index=not args.skip_text_index,
        reset_vector_collection=not args.no_reset,
    )
    print(f"Built vector index for {count} chunks from collection={args.collection}")
    return 0


def vector_query_command(args: argparse.Namespace) -> int:
    results = query_vector_index(
        project_root=Path(args.root),
        query=args.query,
        config_path=Path(args.config) if args.config else None,
        collection=args.collection,
        top_k=args.top_k,
    )
    for index, result in enumerate(results, start=1):
        metadata = result["metadata"]
        print(f"{index}. distance={result['distance']}")
        print(f"   source={metadata.get('path')}:{metadata.get('line_start')}-{metadata.get('line_end')}")
        heading = metadata.get("heading")
        if heading:
            print(f"   heading={heading}")
        preview = result["document"].replace("\n", " ")
        print(f"   {preview[: args.preview_chars]}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local RAG index for Datacon extraction notes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build local RAG index from project sources.")
    build_parser.add_argument("--root", default=".", help="Project root directory.")
    build_parser.add_argument("--index-dir", default="rag_index", help="Output index directory.")
    build_parser.add_argument("--max-chars", type=int, default=1800, help="Maximum chunk size.")
    build_parser.set_defaults(func=build_command)

    query_parser = subparsers.add_parser("query", help="Query local RAG index.")
    query_parser.add_argument("query", help="Search query.")
    query_parser.add_argument("--index-dir", default="rag_index", help="RAG index directory.")
    query_parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to return.")
    query_parser.add_argument("--collection", choices=("project_docs", "methodology_notes", "code_examples", "molecule_facts"))
    query_parser.add_argument("--preview-chars", type=int, default=420)
    query_parser.set_defaults(func=query_command)

    vector_build_parser = subparsers.add_parser("vector-build", help="Build Chroma vector index from RAG chunks.")
    vector_build_parser.add_argument("--root", default=".", help="Project root directory.")
    vector_build_parser.add_argument("--index-dir", default="rag_index", help="Text RAG index directory.")
    vector_build_parser.add_argument("--config", default="config/rag_models.json", help="RAG model config path.")
    vector_build_parser.add_argument("--collection", default="methodology_notes", help="Collection to embed.")
    vector_build_parser.add_argument("--skip-text-index", action="store_true", help="Use existing chunks.jsonl.")
    vector_build_parser.add_argument("--no-reset", action="store_true", help="Do not reset existing Chroma collection.")
    vector_build_parser.set_defaults(func=vector_build_command)

    vector_query_parser = subparsers.add_parser("vector-query", help="Query Chroma vector index.")
    vector_query_parser.add_argument("query", help="Search query.")
    vector_query_parser.add_argument("--root", default=".", help="Project root directory.")
    vector_query_parser.add_argument("--config", default="config/rag_models.json", help="RAG model config path.")
    vector_query_parser.add_argument("--collection", default="methodology_notes", help="Vector collection to query.")
    vector_query_parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to return.")
    vector_query_parser.add_argument("--preview-chars", type=int, default=420)
    vector_query_parser.set_defaults(func=vector_query_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_output_encoding()
    parser = make_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
