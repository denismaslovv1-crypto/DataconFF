from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from rag_core.index import load_chunks
from rag_core.models import RagChunk, SearchResult
from rag_core.text import normalize_whitespace, tokenize


class RagRetriever:
    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.chunks = load_chunks(index_dir)
        self._chunk_terms = [Counter(tokenize(chunk.text)) for chunk in self.chunks]
        self._doc_freq = Counter()
        for terms in self._chunk_terms:
            self._doc_freq.update(terms.keys())
        self._avg_len = sum(sum(terms.values()) for terms in self._chunk_terms) / max(1, len(self._chunk_terms))

    def search(
        self,
        query: str,
        top_k: int = 5,
        collection: str | None = None,
    ) -> list[SearchResult]:
        query_terms = tokenize(query)
        if not query_terms:
            return []

        query_counter = Counter(query_terms)
        scored: list[SearchResult] = []
        for chunk, terms in zip(self.chunks, self._chunk_terms, strict=True):
            if collection and chunk.collection != collection:
                continue
            score = self._bm25_score(terms, query_counter)
            score += self._phrase_boost(query, chunk)
            if score <= 0:
                continue

            matched = sorted(set(query_terms).intersection(terms.keys()))
            scored.append(SearchResult(chunk=chunk, score=round(score, 6), matched_terms=matched))

        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    def _bm25_score(self, terms: Counter[str], query_terms: Counter[str]) -> float:
        score = 0.0
        total_docs = max(1, len(self.chunks))
        doc_len = max(1, sum(terms.values()))
        k1 = 1.5
        b = 0.75

        for term, query_count in query_terms.items():
            tf = terms.get(term, 0)
            if tf == 0:
                continue
            df = self._doc_freq.get(term, 0)
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * doc_len / max(1.0, self._avg_len))
            score += idf * (tf * (k1 + 1) / denominator) * query_count
        return score

    @staticmethod
    def _phrase_boost(query: str, chunk: RagChunk) -> float:
        normalized_query = normalize_whitespace(query).lower()
        if len(normalized_query) < 4:
            return 0.0
        text = normalize_whitespace(chunk.text).lower()
        heading = (chunk.source.heading or "").lower()
        score = 0.0
        if normalized_query in text:
            score += 2.0
        if normalized_query in heading:
            score += 1.0
        return score

