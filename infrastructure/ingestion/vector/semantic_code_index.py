from __future__ import annotations

import hashlib
import os
from pathlib import Path

from infrastructure.evidence.source_indexer import (
    SourceIndexer,
)
from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)
from infrastructure.ingestion.embedding.embedding_model import (
    EmbeddingModel,
)
from infrastructure.ingestion.embedding.huggingface_embedding_model import (
    DEFAULT_HUGGINGFACE_EMBEDDING_MODEL,
    HuggingFaceEmbeddingModel,
)
from infrastructure.ingestion.embedding.late_chunking_text_builder import (
    LateChunkingTextBuilder,
)
from infrastructure.ingestion.vector.sqlite_vector_store import (
    SQLiteVectorStore,
    VectorSearchResult,
)


DEFAULT_VECTOR_DATABASE_PATH = ".swift_agent/vector_index.sqlite3"


class SemanticCodeIndex:

    def __init__(
        self,
        *,
        repository_path: str,
        indexer: SourceIndexer | None = None,
        embedding_model: EmbeddingModel | None = None,
        vector_store: SQLiteVectorStore | None = None,
        text_builder: LateChunkingTextBuilder | None = None,
    ):
        self.repository_path = str(
            Path(repository_path).resolve()
        )
        self.indexer = indexer or SourceIndexer()
        self.embedding_model = (
            embedding_model
            or HuggingFaceEmbeddingModel(
                os.environ.get(
                    "SWIFT_AGENT_EMBEDDING_MODEL",
                    DEFAULT_HUGGINGFACE_EMBEDDING_MODEL,
                )
            )
        )
        self.vector_store = vector_store or SQLiteVectorStore(
            os.environ.get(
                "SWIFT_AGENT_VECTOR_DB_PATH",
                str(
                    Path(self.repository_path)
                    / DEFAULT_VECTOR_DATABASE_PATH
                ),
            )
        )
        self.text_builder = text_builder or LateChunkingTextBuilder()

    def rebuild(self) -> list[CodeChunk]:

        chunks = self.indexer.create_index(
            self.repository_path
        )
        embedding_texts_by_id = self.text_builder.build_many(
            chunks
        )
        records = [
            (
                self._chunk_id(chunk),
                self._content_hash(
                    chunk=chunk,
                    embedding_text=embedding_texts_by_id[id(chunk)],
                ),
                chunk,
                embedding_texts_by_id[id(chunk)],
            )
            for chunk in chunks
        ]
        existing_hashes = self.vector_store.existing_hashes(
            repository_path=self.repository_path,
            model_id=self.embedding_model.model_id,
        )
        records_to_embed = [
            record
            for record in records
            if record[1] not in existing_hashes
        ]

        embeddings = self.embedding_model.embed(
            [
                embedding_text
                for _, _, _, embedding_text in records_to_embed
            ]
        )

        for (
            chunk_id,
            content_hash,
            chunk,
            _,
        ), embedding in zip(records_to_embed, embeddings):
            self.vector_store.upsert(
                chunk_id=chunk_id,
                repository_path=self.repository_path,
                model_id=self.embedding_model.model_id,
                content_hash=content_hash,
                chunk=chunk,
                embedding=embedding,
            )

        return chunks

    def search(
        self,
        query: str,
        *,
        limit: int,
        rebuild: bool = False,
    ) -> list[VectorSearchResult]:

        if rebuild:
            self.rebuild()

        query_embedding = self.embedding_model.embed_one(
            self._query_embedding_text(query)
        )

        return self.vector_store.search(
            repository_path=self.repository_path,
            model_id=self.embedding_model.model_id,
            query_embedding=query_embedding,
            limit=limit,
        )

    def count(self) -> int:

        return self.vector_store.count(
            repository_path=self.repository_path,
            model_id=self.embedding_model.model_id,
        )

    def _chunk_id(
        self,
        chunk: CodeChunk,
    ) -> str:

        key = "|".join(
            [
                self.repository_path,
                chunk.source,
                str(chunk.start_line),
                str(chunk.end_line),
                chunk.qualified_symbol or "",
                chunk.symbol or "",
            ]
        )

        return hashlib.sha256(
            key.encode("utf-8")
        ).hexdigest()

    def _content_hash(
        self,
        *,
        chunk: CodeChunk,
        embedding_text: str,
    ) -> str:

        payload = "|".join(
            [
                self.embedding_model.model_id,
                chunk.source,
                str(chunk.start_line),
                str(chunk.end_line),
                embedding_text,
            ]
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def _query_embedding_text(
        self,
        query: str,
    ) -> str:

        return (
            "Represent this Swift code search query for retrieving "
            f"the most relevant source code chunk:\n{query}"
        )
