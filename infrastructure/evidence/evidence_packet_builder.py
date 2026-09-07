import re
from pathlib import Path

from infrastructure.evidence.evidence_packet import (
    EvidenceFact,
    EvidenceItem,
    EvidencePacket,
)
from infrastructure.evidence.fact_extractor import (
    FactExtractor,
)
from infrastructure.evidence.source_indexer import (
    SourceIndexer,
)
from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)


STOP_WORDS = {
    "a",
    "an",
    "and",
    "class",
    "code",
    "data",
    "does",
    "explain",
    "find",
    "for",
    "get",
    "in",
    "is",
    "it",
    "of",
    "on",
    "repository",
    "responsible",
    "source",
    "the",
    "to",
    "what",
    "where",
    "which",
    "depend",
    "depends",
    "implemented",
    "implementation",
    "obtaining",
}


class EvidencePacketBuilder:

    def __init__(
        self,
        repository_path: str = ".",
        top_k: int = 6,
        top_facts: int = 8,
    ):
        self.repository_path = repository_path
        self.top_k = top_k
        self.top_facts = top_facts
        self.indexer = SourceIndexer()
        self.fact_extractor = FactExtractor()

    def build(
        self,
        query: str,
    ) -> EvidencePacket:

        intent = self._intent(query)
        terms = self._query_terms(query)
        chunks = self.indexer.create_index(
            self.repository_path
        )
        facts = self.fact_extractor.extract(chunks)

        scored_chunks = [
            (
                self._score(
                    chunk=chunk,
                    terms=terms,
                ),
                chunk,
            )
            for chunk in chunks
        ]

        best_chunks = [
            chunk
            for score, chunk in sorted(
                scored_chunks,
                key=lambda item: (
                    item[0],
                    self._symbol_priority(item[1]),
                    -item[1].start_line,
                ),
                reverse=True,
            )
            if score > 0
        ][: self.top_k]

        best_facts = [
            self._with_fact_score(
                fact=fact,
                score=score,
            )
            for score, fact in sorted(
                [
                    (
                        self._score_fact(
                            fact=fact,
                            terms=terms,
                        ),
                        fact,
                    )
                    for fact in facts
                ],
                key=lambda item: item[0],
                reverse=True,
            )
            if score > 0
        ][: self.top_facts]

        best_facts = self._select_facts_for_intent(
            intent=intent,
            facts=best_facts,
            terms=terms,
        )
        best_chunks = self._select_chunks_for_intent(
            intent=intent,
            chunks=best_chunks,
            facts=best_facts,
            terms=terms,
        )

        return EvidencePacket(
            query=query,
            facts=best_facts,
            items=[
                self._to_evidence_item(
                    chunk=chunk,
                    score=self._score(
                        chunk=chunk,
                        terms=terms,
                    ),
                )
                for chunk in best_chunks
            ],
        )

    def _intent(
        self,
        query: str,
    ) -> str:

        query_lower = query.lower()

        if any(
            keyword in query_lower
            for keyword in [
                "depend",
                "depends",
                "dependency",
                "dependencies",
            ]
        ):
            return "dependency"

        if any(
            keyword in query_lower
            for keyword in [
                "responsible",
                "obtaining",
                "fetch",
                "fetched",
            ]
        ):
            return "responsibility"

        if "explain" in query_lower:
            return "method_explanation"

        if any(
            keyword in query_lower
            for keyword in [
                "implemented",
                "implementation",
            ]
        ):
            return "implementation"

        return "general"

    def _query_terms(
        self,
        query: str,
    ) -> set[str]:

        raw_terms = re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*",
            query,
        )
        terms = set()

        for term in raw_terms:
            term_lower = term.lower()

            if term_lower not in STOP_WORDS:
                terms.add(term_lower)

            for part in re.findall(
                r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)",
                term,
            ):
                part_lower = part.lower()

                if part_lower not in STOP_WORDS:
                    terms.add(part_lower)

        return terms

    def _score(
        self,
        chunk: CodeChunk,
        terms: set[str],
    ) -> int:

        searchable = " ".join(
            value
            for value in [
                chunk.source,
                chunk.symbol or "",
                chunk.qualified_symbol or "",
                chunk.symbol_type or "",
                chunk.signature or "",
                chunk.content,
            ]
            if value
        ).lower()

        score = 0

        for term in terms:
            if term not in searchable:
                continue

            score += 1

            if len(term) >= 8:
                score += 10

            if chunk.symbol and term in chunk.symbol.lower():
                score += 8

            if (
                chunk.qualified_symbol
                and term in chunk.qualified_symbol.lower()
            ):
                score += 4

            if term in Path(chunk.source).stem.lower():
                score += 3

        if chunk.symbol:
            score += 2

        if chunk.symbol_type != "line":
            score += 1

        return score

    def _symbol_priority(
        self,
        chunk: CodeChunk,
    ) -> int:

        if chunk.symbol:
            return 2

        if chunk.symbol_type == "line":
            return 1

        return 0

    def _to_evidence_item(
        self,
        chunk: CodeChunk,
        score: int,
    ) -> EvidenceItem:

        return EvidenceItem(
            file=chunk.source,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            score=score,
            content=chunk.content,
            language=chunk.language,
            symbol=chunk.qualified_symbol or chunk.symbol,
            symbol_type=chunk.symbol_type,
            signature=chunk.signature,
        )

    def _select_facts_for_intent(
        self,
        intent: str,
        facts: list[EvidenceFact],
        terms: set[str],
    ) -> list[EvidenceFact]:

        if intent == "dependency":
            dependency_facts = [
                fact
                for fact in facts
                if (
                    fact.kind == "depends_on"
                    and fact.subject != "init"
                    and self._fact_object_matches_terms(
                        fact=fact,
                        terms=terms,
                    )
                )
            ]

            return dependency_facts or facts[:3]

        if intent == "method_explanation":
            call_facts = [
                fact
                for fact in facts
                if (
                    fact.kind == "calls"
                    and self._fact_matches_long_term(
                        fact=fact,
                        terms=terms,
                    )
                )
            ]

            return call_facts[:3]

        if intent == "responsibility":
            useful_facts = [
                fact
                for fact in facts
                if (
                    fact.kind
                    in {
                        "depends_on",
                        "calls",
                        "inherits_or_conforms",
                    }
                    and self._fact_matches_long_term(
                        fact=fact,
                        terms=terms,
                    )
                )
            ]

            return useful_facts[:5]

        return facts

    def _select_chunks_for_intent(
        self,
        intent: str,
        chunks: list[CodeChunk],
        facts: list[EvidenceFact],
        terms: set[str],
    ) -> list[CodeChunk]:

        if intent in {
            "dependency",
            "responsibility",
        } and facts:
            return []

        if intent == "method_explanation":
            implementation_chunks = [
                chunk
                for chunk in chunks
                if (
                    chunk.symbol_type
                    == "function_declaration"
                    and self._matches_terms(
                        chunk=chunk,
                        terms=terms,
                    )
                )
            ]

            if implementation_chunks:
                return implementation_chunks[:1]

        if intent == "implementation":
            implementation_chunks = [
                chunk
                for chunk in chunks
                if (
                    chunk.symbol_type
                    in {
                        "ClassDef",
                        "class_declaration",
                        "protocol_declaration",
                    }
                    and self._chunk_matches_fact_entities(
                        chunk=chunk,
                        facts=facts,
                    )
                )
            ]

            return self._deduplicate_chunks(
                implementation_chunks[:3]
            )

        return chunks[:3]

    def _fact_object_matches_terms(
        self,
        fact: EvidenceFact,
        terms: set[str],
    ) -> bool:

        object_lower = fact.object.lower()

        return any(
            term in object_lower
            for term in terms
            if len(term) >= 6
        )

    def _fact_matches_long_term(
        self,
        fact: EvidenceFact,
        terms: set[str],
    ) -> bool:

        searchable = " ".join(
            [
                fact.subject,
                fact.object,
                fact.evidence,
            ]
        ).lower()

        return any(
            term in searchable
            for term in terms
            if len(term) >= 6
        )

    def _chunk_matches_fact_entities(
        self,
        chunk: CodeChunk,
        facts: list[EvidenceFact],
    ) -> bool:

        symbol = (
            chunk.qualified_symbol
            or chunk.symbol
            or ""
        ).lower()

        if not symbol:
            return False

        entities = {
            fact.subject.lower()
            for fact in facts
        } | {
            fact.object.lower()
            for fact in facts
        }

        return any(
            entity in symbol
            or symbol in entity
            for entity in entities
        )

    def _matches_terms(
        self,
        chunk: CodeChunk,
        terms: set[str],
    ) -> bool:

        symbol = (
            chunk.qualified_symbol
            or chunk.symbol
            or ""
        ).lower()

        return any(
            term in symbol
            for term in terms
            if len(term) >= 6
        )

    def _deduplicate_chunks(
        self,
        chunks: list[CodeChunk],
    ) -> list[CodeChunk]:

        unique = {}

        for chunk in chunks:
            key = (
                chunk.source,
                chunk.start_line,
                chunk.end_line,
                chunk.symbol,
            )
            unique.setdefault(key, chunk)

        return list(unique.values())

    def _score_fact(
        self,
        fact: EvidenceFact,
        terms: set[str],
    ) -> int:

        searchable = " ".join(
            [
                fact.kind,
                fact.subject,
                fact.object,
                fact.file,
                fact.evidence,
            ]
        ).lower()

        score = 0

        for term in terms:
            if term not in searchable:
                continue

            score += 2

            if len(term) >= 8:
                score += 10

            if term in fact.subject.lower():
                score += 8

            if term in fact.object.lower():
                score += 8

            if term in Path(fact.file).stem.lower():
                score += 3

        if score > 0 and fact.kind in {
            "inherits_or_conforms",
            "depends_on",
            "calls",
        }:
            score += 2

        return score

    def _with_fact_score(
        self,
        fact: EvidenceFact,
        score: int,
    ) -> EvidenceFact:

        return EvidenceFact(
            kind=fact.kind,
            subject=fact.subject,
            object=fact.object,
            file=fact.file,
            line=fact.line,
            score=score,
            evidence=fact.evidence,
        )
