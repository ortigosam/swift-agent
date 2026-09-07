from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)

from infrastructure.ingestion.embedding.embedding_text_builder import (
    EmbeddingTextBuilder,
)


chunk = CodeChunk(
    content=(
        "func getCashback() async throws -> Cashback {\n"
        "    try await dataSource.getCashback()\n"
        "}"
    ),
    source="CashbackRepositoryImpl.swift",
    start_line=10,
    end_line=12,
    language="swift",
    symbol="getCashback",
    qualified_symbol=(
        "CashbackRepositoryImpl.getCashback"
    ),
    symbol_type="function_declaration",
    parent_symbol="CashbackRepositoryImpl",
    signature=(
        "func getCashback() async throws -> Cashback"
    ),
    metadata={
        "module": "Cashback",
        "imports": [
            "import Foundation",
            "import Networking",
        ],
        "modifiers": [],
    },
)


builder = EmbeddingTextBuilder()

result = builder.build(chunk)

print(result)