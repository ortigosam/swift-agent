from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)


@dataclass(frozen=True)
class VectorSearchResult:
    chunk: CodeChunk
    score: float


class SQLiteVectorStore:

    def __init__(
        self,
        database_path: str | Path,
    ):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._initialize()

    def upsert(
        self,
        *,
        chunk_id: str,
        repository_path: str,
        model_id: str,
        content_hash: str,
        chunk: CodeChunk,
        embedding: list[float],
    ) -> None:

        metadata_json = json.dumps(
            chunk.metadata,
            ensure_ascii=False,
            sort_keys=True,
        )
        embedding_json = json.dumps(
            embedding,
            separators=(",", ":"),
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO vector_chunks (
                    id,
                    repository_path,
                    model_id,
                    content_hash,
                    source,
                    start_line,
                    end_line,
                    language,
                    symbol,
                    qualified_symbol,
                    symbol_type,
                    parent_symbol,
                    signature,
                    content,
                    context_path,
                    context_path_parts_json,
                    file_path_parts_json,
                    symbol_path_json,
                    metadata_json,
                    embedding_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repository_path = excluded.repository_path,
                    model_id = excluded.model_id,
                    content_hash = excluded.content_hash,
                    source = excluded.source,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    language = excluded.language,
                    symbol = excluded.symbol,
                    qualified_symbol = excluded.qualified_symbol,
                    symbol_type = excluded.symbol_type,
                    parent_symbol = excluded.parent_symbol,
                    signature = excluded.signature,
                    content = excluded.content,
                    context_path = excluded.context_path,
                    context_path_parts_json = excluded.context_path_parts_json,
                    file_path_parts_json = excluded.file_path_parts_json,
                    symbol_path_json = excluded.symbol_path_json,
                    metadata_json = excluded.metadata_json,
                    embedding_json = excluded.embedding_json
                """,
                (
                    chunk_id,
                    repository_path,
                    model_id,
                    content_hash,
                    chunk.source,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.language,
                    chunk.symbol,
                    chunk.qualified_symbol,
                    chunk.symbol_type,
                    chunk.parent_symbol,
                    chunk.signature,
                    chunk.content,
                    chunk.context_path,
                    json.dumps(chunk.context_path_parts),
                    json.dumps(chunk.file_path_parts),
                    json.dumps(chunk.symbol_path),
                    metadata_json,
                    embedding_json,
                ),
            )

    def search(
        self,
        *,
        repository_path: str,
        model_id: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[VectorSearchResult]:

        rows = self._load_rows(
            repository_path=repository_path,
            model_id=model_id,
        )

        scored = []

        for row in rows:
            embedding = json.loads(row["embedding_json"])
            score = self._cosine_similarity(
                query_embedding,
                embedding,
            )
            scored.append(
                VectorSearchResult(
                    chunk=self._row_to_chunk(row),
                    score=score,
                )
            )

        return sorted(
            scored,
            key=lambda item: item.score,
            reverse=True,
        )[:limit]

    def existing_hashes(
        self,
        *,
        repository_path: str,
        model_id: str,
    ) -> set[str]:

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT content_hash
                FROM vector_chunks
                WHERE repository_path = ?
                  AND model_id = ?
                """,
                (
                    repository_path,
                    model_id,
                ),
            ).fetchall()

        return {
            row["content_hash"]
            for row in rows
        }

    def count(
        self,
        *,
        repository_path: str,
        model_id: str,
    ) -> int:

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM vector_chunks
                WHERE repository_path = ?
                  AND model_id = ?
                """,
                (
                    repository_path,
                    model_id,
                ),
            ).fetchone()

        return int(row["total"])

    def _initialize(self) -> None:

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_chunks (
                    id TEXT PRIMARY KEY,
                    repository_path TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    symbol TEXT,
                    qualified_symbol TEXT,
                    symbol_type TEXT,
                    parent_symbol TEXT,
                    signature TEXT,
                    content TEXT NOT NULL,
                    context_path TEXT,
                    context_path_parts_json TEXT NOT NULL,
                    file_path_parts_json TEXT NOT NULL,
                    symbol_path_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_chunks_lookup
                ON vector_chunks(repository_path, model_id)
                """
            )

    def _connect(self) -> sqlite3.Connection:

        connection = sqlite3.connect(
            self.database_path
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _load_rows(
        self,
        *,
        repository_path: str,
        model_id: str,
    ) -> list[sqlite3.Row]:

        with self._connect() as connection:
            return connection.execute(
                """
                SELECT *
                FROM vector_chunks
                WHERE repository_path = ?
                  AND model_id = ?
                """,
                (
                    repository_path,
                    model_id,
                ),
            ).fetchall()

    def _row_to_chunk(
        self,
        row: sqlite3.Row,
    ) -> CodeChunk:

        return CodeChunk(
            content=row["content"],
            source=row["source"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            language=row["language"],
            symbol=row["symbol"],
            qualified_symbol=row["qualified_symbol"],
            symbol_type=row["symbol_type"],
            parent_symbol=row["parent_symbol"],
            context_path=row["context_path"],
            context_path_parts=json.loads(
                row["context_path_parts_json"]
            ),
            file_path_parts=json.loads(
                row["file_path_parts_json"]
            ),
            symbol_path=json.loads(
                row["symbol_path_json"]
            ),
            signature=row["signature"],
            metadata=json.loads(
                row["metadata_json"]
            ),
        )

    def _cosine_similarity(
        self,
        left: list[float],
        right: list[float],
    ) -> float:

        if len(left) != len(right):
            return 0.0

        dot_product = sum(
            left_value * right_value
            for left_value, right_value in zip(left, right)
        )
        left_norm = math.sqrt(
            sum(value * value for value in left)
        )
        right_norm = math.sqrt(
            sum(value * value for value in right)
        )

        if left_norm == 0 or right_norm == 0:
            return 0.0

        return dot_product / (left_norm * right_norm)
