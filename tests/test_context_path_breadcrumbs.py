from infrastructure.evidence.evidence_packet import (
    EvidenceItem,
    EvidencePacket,
)
from infrastructure.ingestion.chunking.ast_chunker import (
    ASTChunker,
)
from infrastructure.ingestion.embedding.embedding_text_builder import (
    EmbeddingTextBuilder,
)
from infrastructure.ingestion.module.module_resolver import (
    ModuleResolver,
)
from infrastructure.ingestion.parser.swift_parser import (
    SwiftParser,
)


class _FakeModuleResolver(ModuleResolver):

    def resolve(
        self,
        source_path: str,
    ) -> str | None:

        return "Cashback"


def test_swift_chunks_include_context_path_breadcrumbs():
    chunks = _swift_chunks()

    method = _chunk_by_qualified_symbol(
        chunks,
        "CashbackRepositoryImpl.getCashback",
    )

    assert method.context_path == (
        "Module: Cashback > "
        "File: Sources/CashbackRepositoryImpl.swift > "
        "Parent: CashbackRepositoryImpl > "
        "Function: func getCashback() async throws -> Cashback"
    )
    assert method.context_path_parts == [
        "Module: Cashback",
        "File: Sources/CashbackRepositoryImpl.swift",
        "Parent: CashbackRepositoryImpl",
        "Function: func getCashback() async throws -> Cashback",
    ]
    assert method.file_path_parts == [
        "Sources",
        "CashbackRepositoryImpl.swift",
    ]
    assert method.symbol_path == [
        "CashbackRepositoryImpl",
        "getCashback",
    ]
    assert method.metadata["context_path"] == method.context_path


def test_extension_children_have_unambiguous_breadcrumbs():
    chunks = _swift_chunks()

    extension = _chunk_by_qualified_symbol(
        chunks,
        "extension CashbackRepositoryImpl",
    )
    method = _chunk_by_qualified_symbol(
        chunks,
        "extension CashbackRepositoryImpl.getAdditionalCashback",
    )

    assert extension.symbol == "CashbackRepositoryImpl"
    assert extension.parent_symbol is None
    assert extension.context_path.endswith(
        "Extension: CashbackRepositoryImpl"
    )
    assert method.parent_symbol == "extension CashbackRepositoryImpl"
    assert method.symbol_path == [
        "extension CashbackRepositoryImpl",
        "getAdditionalCashback",
    ]
    assert (
        "Extension: CashbackRepositoryImpl"
        in method.context_path_parts
    )
    assert method.context_path.endswith(
        "Extension: CashbackRepositoryImpl > "
        "Function: func getAdditionalCashback() async throws -> Cashback"
    )


def test_embedding_and_evidence_include_context_path():
    context_path = (
        "Module: Cashback > File: CashbackRepositoryImpl.swift > "
        "Parent: CashbackRepositoryImpl > Function: getCashback"
    )
    item = EvidenceItem(
        file="CashbackRepositoryImpl.swift",
        start_line=10,
        end_line=12,
        score=42,
        content="func getCashback() {}",
        language="swift",
        symbol="CashbackRepositoryImpl.getCashback",
        symbol_type="function_declaration",
        context_path=context_path,
    )
    packet = EvidencePacket(
        query="get cashback",
        items=[item],
        facts=[],
    )
    chunk = _chunk_by_qualified_symbol(
        _swift_chunks(),
        "CashbackRepositoryImpl.getCashback",
    )

    assert f"Context path: {context_path}" in packet.to_prompt_section()
    assert (
        "Context path: "
        "Module: Cashback > "
        "File: Sources/CashbackRepositoryImpl.swift"
        in EmbeddingTextBuilder().build(chunk)
    )


def _swift_chunks():

    source = """
import Foundation

final class CashbackRepositoryImpl {
    func getCashback() async throws -> Cashback {
        try await dataSource.getCashback()
    }
}

extension CashbackRepositoryImpl {
    func getAdditionalCashback() async throws -> Cashback {
        try await dataSource.getAdditionalCashback()
    }
}
"""

    parser = SwiftParser()
    tree = parser.parse(source)
    chunker = ASTChunker(
        module_resolver=_FakeModuleResolver(),
    )

    return chunker.chunk(
        tree=tree,
        source=source,
        source_path="Sources/CashbackRepositoryImpl.swift",
    )


def _chunk_by_qualified_symbol(
    chunks,
    qualified_symbol: str,
):

    matches = [
        chunk
        for chunk in chunks
        if chunk.qualified_symbol == qualified_symbol
    ]

    assert matches

    return matches[0]


if __name__ == "__main__":
    test_swift_chunks_include_context_path_breadcrumbs()
    test_extension_children_have_unambiguous_breadcrumbs()
    test_embedding_and_evidence_include_context_path()
