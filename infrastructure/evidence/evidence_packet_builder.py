import os
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
from infrastructure.ingestion.vector.semantic_code_index import (
    SemanticCodeIndex,
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

FLOW_KEYWORDS = {
    "before",
    "dispatch",
    "dispatching",
    "flow",
    "handled",
    "handler",
    "happens",
    "starts",
    "when",
}

DOMAIN_TERM_EXPANSIONS = {
    "authentication": {
        "auth",
        "authenticated",
        "authenticationrequired",
        "guard",
        "isloggedin",
        "login",
    },
    "deeplink": {
        "deep",
        "deeplink",
        "deeplinks",
        "deeplinkhandler",
        "deeplinkauthguard",
        "handledeeplink",
        "initializer",
        "matcher",
        "route",
        "url",
    },
    "deeplinks": {
        "deep",
        "deeplink",
        "deeplinks",
        "deeplinkhandler",
        "deeplinkauthguard",
        "handledeeplink",
        "initializer",
        "matcher",
        "route",
        "url",
    },
    "dispatching": {
        "dispatch",
        "handle",
        "handler",
        "navigate",
        "router",
    },
    "flow": {
        "coordinator",
        "flow",
        "start",
        "state",
        "transition",
    },
    "handled": {
        "dispatch",
        "handle",
        "handler",
        "navigate",
        "router",
    },
    "login": {
        "auth",
        "login",
        "postlogin",
        "session",
    },
    "post": {
        "post",
        "postlogin",
    },
    "starts": {
        "start",
        "starts",
        "transition",
    },
}

FLOW_PATH_PARTS = {
    "assembler",
    "authguard",
    "coordinator",
    "deeplink",
    "deeplinks",
    "environment",
    "guard",
    "handler",
    "initializer",
    "inactivity",
    "navigation",
    "router",
    "scenedelegate",
}


class EvidencePacketBuilder:

    def __init__(
        self,
        repository_path: str = ".",
        top_k: int = 6,
        top_facts: int = 8,
        use_vector_search: bool | None = None,
        semantic_index: SemanticCodeIndex | None = None,
    ):
        self.repository_path = repository_path
        self.top_k = top_k
        self.top_facts = top_facts
        self.indexer = SourceIndexer()
        self.fact_extractor = FactExtractor()
        self.use_vector_search = (
            use_vector_search
            if use_vector_search is not None
            else os.environ.get(
                "SWIFT_AGENT_VECTOR_SEARCH",
                "",
            ).lower()
            in {
                "1",
                "true",
                "yes",
            }
        )
        self.semantic_index = semantic_index

    def build(
        self,
        query: str,
    ) -> EvidencePacket:

        if self.use_vector_search:
            semantic_packet = self._semantic_packet(query)

            if semantic_packet is not None:
                return semantic_packet

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
                    intent=intent,
                ),
                chunk,
            )
            for chunk in chunks
        ]

        chunk_candidate_limit = max(
            self.top_k * 6,
            30,
        )
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
        ][:chunk_candidate_limit]

        if self.use_vector_search:
            best_chunks = self._merge_semantic_chunks(
                query=query,
                chunks=best_chunks,
            )

        fact_candidate_limit = max(
            self.top_facts * 6,
            30,
        )
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
                            intent=intent,
                        ),
                        fact,
                    )
                    for fact in facts
                ],
                key=lambda item: item[0],
                reverse=True,
            )
            if score > 0
        ][:fact_candidate_limit]

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
                        intent=intent,
                    ),
                )
                for chunk in best_chunks
            ],
        )

    def _semantic_packet(
        self,
        query: str,
    ) -> EvidencePacket | None:

        intent = self._intent(query)
        terms = self._query_terms(query)
        semantic_index = self.semantic_index or SemanticCodeIndex(
            repository_path=self.repository_path,
        )

        semantic_results = semantic_index.search(
            query,
            limit=max(self.top_k * 6, 30),
            rebuild=self._vector_rebuild_enabled(),
        )

        if not semantic_results:
            return None

        score_by_chunk = {
            self._chunk_key(result.chunk): result.score
            for result in semantic_results
        }
        semantic_chunks = [
            result.chunk
            for result in semantic_results
            if result.score > 0
        ]

        selected_chunks = self._select_semantic_chunks(
            intent=intent,
            chunks=semantic_chunks,
            terms=terms,
        )

        items = [
            self._to_semantic_evidence_item(
                chunk=chunk,
                score=self._vector_score(
                    score_by_chunk.get(
                        self._chunk_key(chunk),
                        0,
                    )
                ),
                terms=terms,
            )
            for chunk in selected_chunks
        ][: self._semantic_top_k()]

        if not items:
            return None

        return EvidencePacket(
            query=query,
            facts=[],
            items=items,
        )

    def _to_semantic_evidence_item(
        self,
        chunk: CodeChunk,
        score: int,
        terms: set[str],
    ) -> EvidenceItem:

        item = self._to_evidence_item(
            chunk=chunk,
            score=score,
        )

        if chunk.symbol_type != "file":
            return item

        compact_content = self._compact_file_chunk_content(
            content=item.content,
            terms=terms,
            symbol=item.symbol,
        )

        symbol = item.symbol
        declarations = self._declarations_in_content(
            compact_content
        )

        if declarations:
            symbol = ", ".join(
                [
                    value
                    for value in [
                        item.symbol,
                        *declarations,
                    ]
                    if value
                ]
            )
            compact_content = (
                "Declarations: "
                + ", ".join(declarations)
                + "\n"
                + compact_content
            )

        return EvidenceItem(
            file=item.file,
            start_line=item.start_line,
            end_line=item.end_line,
            score=item.score,
            content=compact_content,
            language=item.language,
            symbol=symbol,
            symbol_type=item.symbol_type,
            signature=item.signature,
            context_path=item.context_path,
        )

    def _declarations_in_content(
        self,
        content: str,
    ) -> list[str]:

        declarations = []

        for match in re.finditer(
            r"\b(?:class|struct|enum|protocol)\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)",
            content,
        ):
            declarations.append(match.group(1))

        return list(
            dict.fromkeys(declarations)
        )

    def _compact_file_chunk_content(
        self,
        content: str,
        terms: set[str],
        symbol: str | None,
    ) -> str:

        lines = content.splitlines()
        selected_indexes: set[int] = set()

        declaration_pattern = re.compile(
            r"\b(class|struct|enum|protocol)\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
        )
        meaningful_terms = {
            term
            for term in terms
            if len(term) >= 6
        }
        symbol_lower = (
            symbol or ""
        ).lower()

        for index, line in enumerate(lines):
            line_lower = line.lower()
            declaration_match = declaration_pattern.search(line)

            if declaration_match:
                declaration_name = declaration_match.group(2)
                declaration_name_lower = declaration_name.lower()

                if (
                    (
                        symbol_lower
                        and symbol_lower in declaration_name_lower
                    )
                    or declaration_name.startswith("Default")
                    or any(
                        term in line_lower
                        for term in meaningful_terms
                    )
                ):
                    selected_indexes.update(
                        self._line_window(
                            index=index,
                            line_count=len(lines),
                            before=1,
                            after=3,
                        )
                    )

                continue

            if line_lower.lstrip().startswith("import "):
                continue

            if any(term in line_lower for term in meaningful_terms):
                selected_indexes.update(
                    self._line_window(
                        index=index,
                        line_count=len(lines),
                        before=4,
                        after=8,
                    )
                )

        if not selected_indexes:
            return content

        return self._join_compacted_lines(
            lines=lines,
            selected_indexes=selected_indexes,
        )

    def _line_window(
        self,
        *,
        index: int,
        line_count: int,
        before: int,
        after: int,
    ) -> set[int]:

        return set(
            range(
                max(0, index - before),
                min(line_count, index + after + 1),
            )
        )

    def _join_compacted_lines(
        self,
        *,
        lines: list[str],
        selected_indexes: set[int],
    ) -> str:

        result = []
        previous_index = None

        for index in sorted(selected_indexes):
            if (
                previous_index is not None
                and index > previous_index + 1
            ):
                result.append("...")

            result.append(lines[index])
            previous_index = index

        return "\n".join(result)

    def _select_semantic_chunks(
        self,
        intent: str,
        chunks: list[CodeChunk],
        terms: set[str],
    ) -> list[CodeChunk]:

        if intent == "flow_tracing":
            flow_chunks = [
                chunk
                for chunk in chunks
                if self._is_flow_chunk(
                    chunk=chunk,
                    terms=terms,
                )
            ]

            return self._diversify_chunks(
                flow_chunks or chunks,
                limit=self._semantic_top_k(),
                max_per_file=1,
            )

        return self._diversify_chunks(
            chunks,
            limit=self._semantic_top_k(),
            max_per_file=1,
        )

    def _semantic_top_k(self) -> int:

        configured = int(
            os.environ.get(
                "SWIFT_AGENT_VECTOR_TOP_K",
                "6",
            )
        )

        return max(
            1,
            min(
                self.top_k,
                configured,
            ),
        )

    def _merge_semantic_chunks(
        self,
        query: str,
        chunks: list[CodeChunk],
    ) -> list[CodeChunk]:

        semantic_index = self.semantic_index or SemanticCodeIndex(
            repository_path=self.repository_path,
            indexer=self.indexer,
        )

        semantic_results = semantic_index.search(
            query,
            limit=max(self.top_k * 3, 12),
            rebuild=self._vector_rebuild_enabled(),
        )

        return self._deduplicate_chunks(
            [
                result.chunk
                for result in semantic_results
                if result.score > 0
            ]
            + chunks
        )

    def _vector_rebuild_enabled(self) -> bool:

        return os.environ.get(
            "SWIFT_AGENT_VECTOR_REBUILD",
            "",
        ).lower() in {
            "1",
            "true",
            "yes",
        }

    def _vector_score(
        self,
        score: float,
    ) -> int:

        return int(score * 1000)

    def _intent(
        self,
        query: str,
    ) -> str:

        query_lower = query.lower()

        if self._is_flow_query(query_lower):
            return "flow_tracing"

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

    def _is_flow_query(
        self,
        query_lower: str,
    ) -> bool:

        if any(
            keyword in query_lower
            for keyword in FLOW_KEYWORDS
        ):
            return True

        return any(
            keyword in query_lower
            for keyword in [
                "post-login",
                "post login",
                "deeplink",
                "deep link",
            ]
        )

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

        self._expand_query_terms(terms)

        return terms

    def _expand_query_terms(
        self,
        terms: set[str],
    ) -> None:

        expanded = set()

        for term in terms:
            expanded.update(
                DOMAIN_TERM_EXPANSIONS.get(
                    term,
                    set(),
                )
            )

        if {
            "post",
            "login",
        }.issubset(terms):
            expanded.add("postlogin")

        terms.update(expanded)

    def _score(
        self,
        chunk: CodeChunk,
        terms: set[str],
        intent: str = "general",
    ) -> int:

        searchable = " ".join(
            value
            for value in [
                chunk.source,
                chunk.symbol or "",
                chunk.qualified_symbol or "",
                chunk.symbol_type or "",
                chunk.signature or "",
                self._chunk_context_search_text(chunk),
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

        if intent == "flow_tracing":
            score += self._flow_chunk_boost(
                chunk=chunk,
                terms=terms,
                searchable=searchable,
            )

        score -= self._path_penalty(chunk.source)

        return score

    def _flow_chunk_boost(
        self,
        chunk: CodeChunk,
        terms: set[str],
        searchable: str,
    ) -> int:

        score = 0
        path_parts = self._path_parts(chunk.source)
        symbol = (
            chunk.qualified_symbol
            or chunk.symbol
            or ""
        ).lower()

        if path_parts & FLOW_PATH_PARTS:
            score += 8

        if chunk.symbol_type in {
            "function_declaration",
            "init_declaration",
        }:
            score += 4

        if chunk.symbol_type == "file" and any(
            term in searchable
            for term in terms
            if len(term) >= 6
        ):
            score += 8

        if any(
            word in symbol
            for word in [
                "handle",
                "start",
                "transition",
                "navigate",
                "dispatch",
            ]
        ):
            score += 10

        if "deeplink" in terms and any(
            word in searchable
            for word in [
                "handledeeplink",
                "deeplinkauthguard",
                "authenticationrequired",
                "pendingdeeplink",
            ]
        ):
            score += 15

        if "postlogin" in terms and any(
            word in searchable
            for word in [
                "postlogin",
                "pendingdeeplink",
                "navigatetotabbar",
                "inactivitymanager",
            ]
        ):
            score += 15

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
            context_path=(
                chunk.context_path
                or chunk.metadata.get("context_path")
            ),
        )

    def _select_facts_for_intent(
        self,
        intent: str,
        facts: list[EvidenceFact],
        terms: set[str],
    ) -> list[EvidenceFact]:

        if intent == "flow_tracing":
            flow_facts = [
                fact
                for fact in facts
                if (
                    fact.kind
                    in {
                        "calls",
                        "depends_on",
                        "inherits_or_conforms",
                    }
                    and self._fact_matches_long_term(
                        fact=fact,
                        terms=terms,
                    )
                )
            ]

            return flow_facts[: self.top_facts]

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

        if intent == "flow_tracing":
            return self._select_flow_chunks(
                chunks=chunks,
                facts=facts,
                terms=terms,
            )

        if intent == "responsibility" and facts:
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
                return implementation_chunks[
                    : self.top_k
                ]

        if intent == "implementation":
            implementation_chunks = [
                chunk
                for chunk in chunks
                if (
                    chunk.symbol_type
                    in {
                        "ClassDef",
                        "class_declaration",
                        "struct_declaration",
                        "enum_declaration",
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

        return self._diversify_chunks(
            chunks,
            limit=min(
                self.top_k,
                3,
            ),
        )

    def _select_flow_chunks(
        self,
        chunks: list[CodeChunk],
        facts: list[EvidenceFact],
        terms: set[str],
    ) -> list[CodeChunk]:

        fact_files = {
            fact.file
            for fact in facts
        }
        flow_chunks = [
            chunk
            for chunk in chunks
            if (
                chunk.source in fact_files
                or self._chunk_matches_fact_entities(
                    chunk=chunk,
                    facts=facts,
                )
                or self._is_flow_chunk(
                    chunk=chunk,
                    terms=terms,
                )
            )
        ]

        selected = self._diversify_chunks(
            flow_chunks or chunks,
            limit=self.top_k,
        )

        return selected

    def _is_flow_chunk(
        self,
        chunk: CodeChunk,
        terms: set[str],
    ) -> bool:

        searchable = " ".join(
            value
            for value in [
                chunk.source,
                chunk.symbol or "",
                chunk.qualified_symbol or "",
                self._chunk_context_search_text(chunk),
                chunk.content,
            ]
            if value
        ).lower()

        if self._path_parts(chunk.source) & FLOW_PATH_PARTS:
            return True

        if "deeplink" in terms and any(
            value in searchable
            for value in [
                "handledeeplink",
                "deeplinkauthguard",
                "authenticationrequired",
                "pendingdeeplink",
            ]
        ):
            return True

        if "postlogin" in terms and any(
            value in searchable
            for value in [
                "postlogin",
                "pendingdeeplink",
                "navigatetotabbar",
                "inactivitymanager",
            ]
        ):
            return True

        return False

    def _diversify_chunks(
        self,
        chunks: list[CodeChunk],
        limit: int,
        max_per_file: int = 2,
    ) -> list[CodeChunk]:

        selected = []
        count_by_file: dict[str, int] = {}

        for chunk in self._deduplicate_chunks(chunks):
            file_count = count_by_file.get(
                chunk.source,
                0,
            )

            if file_count >= max_per_file:
                continue

            selected.append(chunk)
            count_by_file[chunk.source] = file_count + 1

            if len(selected) >= limit:
                return selected

        return selected

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

    def _chunk_key(
        self,
        chunk: CodeChunk,
    ) -> tuple:

        return (
            chunk.source,
            chunk.start_line,
            chunk.end_line,
            chunk.symbol,
        )

    def _score_fact(
        self,
        fact: EvidenceFact,
        terms: set[str],
        intent: str = "general",
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

        if intent == "flow_tracing":
            score += self._flow_fact_boost(
                fact=fact,
                terms=terms,
                searchable=searchable,
            )

        score -= self._path_penalty(fact.file)

        return score

    def _flow_fact_boost(
        self,
        fact: EvidenceFact,
        terms: set[str],
        searchable: str,
    ) -> int:

        score = 0

        if self._path_parts(fact.file) & FLOW_PATH_PARTS:
            score += 8

        if fact.kind == "calls":
            score += 6

        if "deeplink" in terms and any(
            word in searchable
            for word in [
                "handledeeplink",
                "deeplinkauthguard",
                "authenticationrequired",
                "pendingdeeplink",
            ]
        ):
            score += 15

        if "postlogin" in terms and any(
            word in searchable
            for word in [
                "postlogin",
                "pendingdeeplink",
                "navigatetotabbar",
                "inactivitymanager",
            ]
        ):
            score += 15

        return score

    def _path_penalty(
        self,
        path: str,
    ) -> int:

        parts = self._path_parts(path)

        if any(
            part in {
                "tests",
                "__tests__",
                "pods",
                ".build",
            }
            or part.endswith("tests")
            for part in parts
        ):
            return 25

        return 0

    def _path_parts(
        self,
        path: str,
    ) -> set[str]:

        return {
            part.lower()
            for part in Path(path).parts
        }

    def _chunk_context_search_text(
        self,
        chunk: CodeChunk,
    ) -> str:

        values = []
        metadata = chunk.metadata

        context_path = (
            chunk.context_path
            or metadata.get("context_path")
        )
        if context_path:
            values.append(context_path)

        values.extend(chunk.context_path_parts)
        values.extend(chunk.file_path_parts)
        values.extend(chunk.symbol_path)

        for key in [
            "context_path_parts",
            "file_path_parts",
            "symbol_path",
        ]:
            items = metadata.get(key, [])
            if items:
                values.extend(str(item) for item in items)

        return " ".join(values)

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
