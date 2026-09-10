from infrastructure.evidence.evidence_packet import (
    EvidenceFact,
)
from infrastructure.evidence.evidence_packet_builder import (
    EvidencePacketBuilder,
)
from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)


class _FakeIndexer:

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


class _FakeFactExtractor:

    def __init__(
        self,
        facts: list[EvidenceFact],
    ):
        self.facts = facts

    def extract(
        self,
        chunks: list[CodeChunk],
    ) -> list[EvidenceFact]:

        return self.facts


def test_flow_retrieval_keeps_deeplink_coordinator_context():
    packet = _build_packet(
        query=(
            "Find where deeplinks are handled and explain how "
            "authentication is enforced before dispatching a deeplink."
        ),
        chunks=[
            _chunk(
                source=(
                    "APPIMA/Navigation/Deeplinks/"
                    "DeepLinkHandlerAssembler.swift"
                ),
                symbol="DeepLinkHandlerAssembler.extractDeepLinkPath",
                symbol_type="function_declaration",
                content="func extractDeepLinkPath(from url: URL) {}",
            ),
            _chunk(
                source="APPIMA/Navigation/AppCoordinator.swift",
                symbol="AppCoordinator",
                symbol_type="file",
                content=(
                    "func handleDeeplink(deeplink: URL) async {\n"
                    "    pendingDeeplink = deeplink\n"
                    "    await transition(to: .postLogin)\n"
                    "}\n"
                    "case .postLogin: break"
                ),
            ),
        ],
        facts=[
            EvidenceFact(
                kind="calls",
                subject="SceneDelegate.navigateToDeeplink",
                object="appCoordinator.handleDeeplink",
                file="APPIMA/AppDelegate/SceneDelegate.swift",
                line=116,
                score=0,
                evidence=(
                    "appCoordinator.handleDeeplink(deeplink: url)"
                ),
            )
        ],
    )

    files = {
        item.file
        for item in packet.items
    }

    assert "APPIMA/Navigation/AppCoordinator.swift" in files
    assert (
        "APPIMA/Navigation/Deeplinks/"
        "DeepLinkHandlerAssembler.swift"
    ) in files


def test_flow_retrieval_boosts_post_login_file_chunks():
    packet = _build_packet(
        query=(
            "Find the post-login coordinator implementation and "
            "explain what happens when the post-login flow starts."
        ),
        chunks=[
            _chunk(
                source=(
                    "Features/BaseModule/Sources/BaseModule/"
                    "BaseModuleCoordinator.swift"
                ),
                symbol=(
                    "DefaultBaseModuleCoordinator."
                    "startSwiftUIFlow"
                ),
                symbol_type="function_declaration",
                content="func startSwiftUIFlow() { coordinator.start() }",
            ),
            _chunk(
                source="APPIMA/Navigation/AppCoordinator.swift",
                symbol="AppCoordinator",
                symbol_type="file",
                content=(
                    "private var pendingDeeplink: URL?\n"
                    "case .postLogin:\n"
                    "inactivityManager.setActive(true)\n"
                    "navigateToTabbar()"
                ),
            ),
        ],
        facts=[],
    )

    assert packet.items[0].file == (
        "APPIMA/Navigation/AppCoordinator.swift"
    )


def _build_packet(
    query: str,
    chunks: list[CodeChunk],
    facts: list[EvidenceFact],
):

    builder = EvidencePacketBuilder(
        repository_path=".",
        top_k=4,
        top_facts=4,
    )
    builder.indexer = _FakeIndexer(chunks)
    builder.fact_extractor = _FakeFactExtractor(facts)

    return builder.build(query)


def _chunk(
    source: str,
    symbol: str,
    symbol_type: str,
    content: str,
) -> CodeChunk:

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
        qualified_symbol=symbol,
        symbol_type=symbol_type,
    )


if __name__ == "__main__":
    test_flow_retrieval_keeps_deeplink_coordinator_context()
    test_flow_retrieval_boosts_post_login_file_chunks()
