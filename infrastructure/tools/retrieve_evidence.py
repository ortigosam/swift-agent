from langchain_core.tools import tool

from infrastructure.evidence.evidence_packet_builder import (
    EvidencePacketBuilder,
)


@tool
def retrieve_evidence(
    query: str,
) -> str:
    """Retrieve indexed repository evidence chunks for a code question."""

    if not query.strip():
        return "No query provided."

    builder = EvidencePacketBuilder(
        repository_path=".",
        top_k=8,
        top_facts=8,
    )
    evidence_packet = builder.build(query)

    return evidence_packet.to_prompt_section(
        max_chars_per_item=1200,
    )
