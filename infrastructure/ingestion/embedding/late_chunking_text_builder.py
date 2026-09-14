from __future__ import annotations

from collections import defaultdict

from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)
from infrastructure.ingestion.embedding.embedding_text_builder import (
    EmbeddingTextBuilder,
)


class LateChunkingTextBuilder:
    """
    Builds chunk embedding text with document-level context.

    The AST chunk boundaries remain unchanged. The extra file outline gives
    each chunk enough surrounding context for semantic retrieval without
    merging unrelated declarations.
    """

    def __init__(
        self,
        base_builder: EmbeddingTextBuilder | None = None,
        max_outline_symbols: int = 32,
    ):
        self.base_builder = base_builder or EmbeddingTextBuilder()
        self.max_outline_symbols = max_outline_symbols

    def build_many(
        self,
        chunks: list[CodeChunk],
    ) -> dict[int, str]:

        chunks_by_source: dict[str, list[CodeChunk]] = defaultdict(list)

        for chunk in chunks:
            chunks_by_source[chunk.source].append(chunk)

        return {
            id(chunk): self.build(
                chunk=chunk,
                file_chunks=chunks_by_source[chunk.source],
            )
            for chunk in chunks
        }

    def build(
        self,
        chunk: CodeChunk,
        file_chunks: list[CodeChunk],
    ) -> str:

        sections = [
            self._file_outline(file_chunks),
            self.base_builder.build(chunk),
        ]

        return "\n\n".join(
            section
            for section in sections
            if section
        )

    def _file_outline(
        self,
        file_chunks: list[CodeChunk],
    ) -> str:

        symbols = []

        for chunk in sorted(
            file_chunks,
            key=lambda item: item.start_line,
        ):
            symbol = (
                chunk.qualified_symbol
                or chunk.symbol
            )

            if not symbol:
                continue

            label = symbol

            if chunk.signature:
                label = chunk.signature

            symbols.append(
                f"- {chunk.symbol_type or 'symbol'}: {label}"
            )

            if len(symbols) >= self.max_outline_symbols:
                break

        if not symbols:
            return ""

        return (
            "File outline for late chunking context:\n"
            + "\n".join(symbols)
        )
