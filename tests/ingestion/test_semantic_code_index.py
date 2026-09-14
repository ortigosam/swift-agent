from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.evidence.evidence_packet_builder import (
    EvidencePacketBuilder,
)
from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)
from infrastructure.ingestion.embedding.embedding_model import (
    EmbeddingModel,
)
from infrastructure.ingestion.embedding.late_chunking_text_builder import (
    LateChunkingTextBuilder,
)
from infrastructure.ingestion.vector.semantic_code_index import (
    SemanticCodeIndex,
)
from infrastructure.ingestion.vector.sqlite_vector_store import (
    SQLiteVectorStore,
)


class FakeEmbeddingModel(EmbeddingModel):

    @property
    def model_id(self) -> str:
        return "fake-code-embedding"

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        return [
            self._embed_text(text)
            for text in texts
        ]

    def _embed_text(
        self,
        text: str,
    ) -> list[float]:

        lowered = text.lower()

        return [
            float("deeplink" in lowered),
            float("auth" in lowered),
            float("cashback" in lowered),
        ]


class FakeIndexer:

    def __init__(
        self,
        chunks: list[CodeChunk],
    ):
        self.chunks = chunks

    def create_index(
        self,
        repository_path: str,
    ) -> list[CodeChunk]:

        return self.chunks


class FailingIndexer:

    def create_index(
        self,
        repository_path: str,
    ) -> list[CodeChunk]:

        raise AssertionError(
            "Vector search should not rebuild the lexical index "
            "when semantic results are already available."
        )


def test_late_chunking_embedding_text_keeps_file_outline():
    chunks = [
        _chunk(
            source="APPIMA/Navigation/AppCoordinator.swift",
            symbol="DefaultAppCoordinator",
            content="final class DefaultAppCoordinator {}",
        ),
        _chunk(
            source="APPIMA/Navigation/AppCoordinator.swift",
            symbol="handleDeeplink",
            content="func handleDeeplink(deeplink: URL) async {}",
            parent_symbol="DefaultAppCoordinator",
            signature=(
                "func handleDeeplink(deeplink: URL) async"
            ),
        ),
    ]

    text = LateChunkingTextBuilder().build(
        chunk=chunks[1],
        file_chunks=chunks,
    )

    assert "File outline for late chunking context" in text
    assert "DefaultAppCoordinator" in text
    assert "func handleDeeplink(deeplink: URL) async" in text
    assert "Context path:" in text


def test_semantic_code_index_returns_vector_matches():
    with TemporaryDirectory() as directory:
        chunks = [
            _chunk(
                source="APPIMA/Navigation/Deeplinks/AppDeepLinkAuthGuard.swift",
                symbol="AppDeepLinkAuthGuard",
                content=(
                    "struct AppDeepLinkAuthGuard { "
                    "func isAuthenticated() async -> Bool { true } "
                    "}"
                ),
            ),
            _chunk(
                source="APPIMA/Features/Cashback/CashbackRepository.swift",
                symbol="CashbackRepository",
                content="protocol CashbackRepository {}",
            ),
        ]
        semantic_index = SemanticCodeIndex(
            repository_path=directory,
            indexer=FakeIndexer(chunks),
            embedding_model=FakeEmbeddingModel(),
            vector_store=SQLiteVectorStore(
                Path(directory) / "vectors.sqlite3"
            ),
        )

        results = semantic_index.search(
            "where is deeplink authentication checked",
            limit=1,
            rebuild=True,
        )

        assert results
        assert results[0].chunk.symbol == "AppDeepLinkAuthGuard"


def test_evidence_packet_builder_can_use_semantic_index():
    with TemporaryDirectory() as directory:
        chunks = [
            _chunk(
                source="APPIMA/Features/Cashback/CashbackRepository.swift",
                symbol="CashbackRepository",
                content="protocol CashbackRepository {}",
            ),
            _chunk(
                source="APPIMA/Navigation/Deeplinks/AppDeepLinkAuthGuard.swift",
                symbol="AppDeepLinkAuthGuard",
                content=(
                    "struct AppDeepLinkAuthGuard { "
                    "func isAuthenticated() async -> Bool { true } "
                    "}"
                ),
            ),
        ]
        indexer = FakeIndexer(chunks)
        semantic_index = SemanticCodeIndex(
            repository_path=directory,
            indexer=indexer,
            embedding_model=FakeEmbeddingModel(),
            vector_store=SQLiteVectorStore(
                Path(directory) / "vectors.sqlite3"
            ),
        )
        builder = EvidencePacketBuilder(
            repository_path=directory,
            top_k=2,
            top_facts=0,
            use_vector_search=True,
            semantic_index=semantic_index,
        )
        builder.indexer = indexer
        semantic_index.rebuild()

        packet = builder.build(
            "where is deeplink authentication checked"
        )

        assert packet.items
        assert packet.items[0].symbol == "AppDeepLinkAuthGuard"


def test_vector_evidence_packet_does_not_call_lexical_indexer():
    with TemporaryDirectory() as directory:
        chunks = [
            _chunk(
                source="APPIMA/Navigation/Deeplinks/AppDeepLinkAuthGuard.swift",
                symbol="AppDeepLinkAuthGuard",
                content=(
                    "struct AppDeepLinkAuthGuard { "
                    "func isAuthenticated() async -> Bool { true } "
                    "}"
                ),
            ),
        ]
        semantic_index = SemanticCodeIndex(
            repository_path=directory,
            indexer=FakeIndexer(chunks),
            embedding_model=FakeEmbeddingModel(),
            vector_store=SQLiteVectorStore(
                Path(directory) / "vectors.sqlite3"
            ),
        )
        semantic_index.rebuild()

        builder = EvidencePacketBuilder(
            repository_path=directory,
            top_k=2,
            top_facts=0,
            use_vector_search=True,
            semantic_index=semantic_index,
        )
        builder.indexer = FailingIndexer()

        packet = builder.build(
            "where is deeplink authentication checked"
        )

        assert packet.items
        assert packet.facts == []


def test_semantic_file_chunks_are_compacted_around_context():
    chunk = CodeChunk(
        content=(
            "import Foundation\n"
            "\n"
            "final class MainNavigationDelegate {}\n"
            "\n"
            "final class DefaultAppCoordinator {\n"
            "    private var pendingDeeplink: URL?\n"
            "\n"
            "    func handleDeeplink(deeplink: URL) async {\n"
            "        try await deepLinkHandler.handle(uri: deeplink.absoluteString)\n"
            "    }\n"
            "}\n"
        ),
        source="APPIMA/Navigation/AppCoordinator.swift",
        start_line=1,
        end_line=11,
        language="swift",
        symbol="AppCoordinator",
        qualified_symbol="AppCoordinator",
        symbol_type="file",
    )
    builder = EvidencePacketBuilder()
    item = builder._to_semantic_evidence_item(
        chunk=chunk,
        score=1,
        terms={
            "deeplink",
            "authentication",
        },
    )

    assert "DefaultAppCoordinator" in item.content
    assert "handleDeeplink" in item.content


def _chunk(
    *,
    source: str,
    symbol: str,
    content: str,
    parent_symbol: str | None = None,
    signature: str | None = None,
) -> CodeChunk:

    context_path_parts = [
        "Module: ADAM_ENT_FULL",
        f"File: {source}",
    ]

    if parent_symbol:
        context_path_parts.append(
            f"Parent: {parent_symbol}"
        )

    context_path_parts.append(
        f"Symbol: {symbol}"
    )

    return CodeChunk(
        content=content,
        source=source,
        start_line=1,
        end_line=max(
            1,
            len(content.splitlines()),
        ),
        language="swift",
        symbol=symbol,
        qualified_symbol=(
            f"{parent_symbol}.{symbol}"
            if parent_symbol
            else symbol
        ),
        symbol_type="function_declaration",
        parent_symbol=parent_symbol,
        context_path=" > ".join(context_path_parts),
        context_path_parts=context_path_parts,
        file_path_parts=list(Path(source).parts),
        symbol_path=[
            item
            for item in [
                parent_symbol,
                symbol,
            ]
            if item
        ],
        signature=signature,
        metadata={
            "module": "ADAM_ENT_FULL",
            "context_path": " > ".join(context_path_parts),
        },
    )


if __name__ == "__main__":
    test_late_chunking_embedding_text_keeps_file_outline()
    test_semantic_code_index_returns_vector_matches()
    test_evidence_packet_builder_can_use_semantic_index()
    test_vector_evidence_packet_does_not_call_lexical_indexer()
    test_semantic_file_chunks_are_compacted_around_context()
