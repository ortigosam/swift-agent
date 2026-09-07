import re

from infrastructure.evidence.evidence_packet import (
    EvidenceFact,
)
from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)


class FactExtractor:

    def extract(
        self,
        chunks: list[CodeChunk],
    ) -> list[EvidenceFact]:

        facts = []

        for chunk in chunks:
            if chunk.language == "swift":
                facts.extend(
                    self._extract_swift_facts(chunk)
                )

            if chunk.language == "python":
                facts.extend(
                    self._extract_python_facts(chunk)
                )

        return self._deduplicate(facts)

    def _extract_swift_facts(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        facts = []

        facts.extend(
            self._extract_metadata_type_relations(chunk)
        )
        facts.extend(
            self._extract_metadata_dependencies(chunk)
        )
        facts.extend(
            self._extract_metadata_calls(chunk)
        )

        if facts:
            return facts

        if chunk.symbol_type in {
            "class_declaration",
            "struct_declaration",
            "enum_declaration",
        }:
            facts.extend(
                self._extract_swift_type_relations(chunk)
            )
            facts.extend(
                self._extract_swift_dependencies(chunk)
            )

        if chunk.symbol_type in {
            "function_declaration",
            "init_declaration",
        }:
            facts.extend(
                self._extract_swift_calls(chunk)
            )

        return facts

    def _extract_metadata_type_relations(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        subject = chunk.symbol

        if subject is None:
            return []

        return [
            EvidenceFact(
                kind="inherits_or_conforms",
                subject=subject,
                object=item["type"],
                file=chunk.source,
                line=item["line"],
                score=0,
                evidence=item["evidence"],
            )
            for item in chunk.metadata.get(
                "inherits_or_conforms",
                [],
            )
        ]

    def _extract_metadata_dependencies(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        subject = chunk.symbol

        if subject is None:
            return []

        return [
            EvidenceFact(
                kind="depends_on",
                subject=subject,
                object=item["type"],
                file=chunk.source,
                line=item["line"],
                score=0,
                evidence=item["evidence"],
            )
            for item in chunk.metadata.get(
                "dependencies",
                [],
            )
        ]

    def _extract_metadata_calls(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        subject = chunk.qualified_symbol or chunk.symbol

        if subject is None:
            return []

        return [
            EvidenceFact(
                kind="calls",
                subject=subject,
                object=item["target"],
                file=chunk.source,
                line=item["line"],
                score=0,
                evidence=item["evidence"],
            )
            for item in chunk.metadata.get(
                "calls",
                [],
            )
        ]

    def _extract_swift_type_relations(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        declaration = self._first_declaration_line(
            chunk.content
        )
        match = re.search(
            r"\b(?:class|struct|enum)\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
            r"\s*:\s*([^{\n]+)",
            declaration,
        )

        if match is None:
            return []

        subject = match.group(1)
        related_types = self._split_swift_type_list(
            match.group(2)
        )

        return [
            self._fact(
                kind="inherits_or_conforms",
                subject=subject,
                object=related_type,
                chunk=chunk,
                evidence=declaration,
            )
            for related_type in related_types
        ]

    def _extract_swift_dependencies(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        subject = chunk.symbol

        if subject is None:
            return []

        facts = []

        for line_number, line in self._iter_lines(chunk):
            property_match = re.search(
                r"\b(?:let|var)\s+"
                r"([A-Za-z_][A-Za-z0-9_]*)"
                r"\s*:\s*"
                r"([A-Za-z_][A-Za-z0-9_.<>]*)",
                line,
            )

            if property_match is not None:
                facts.append(
                    EvidenceFact(
                        kind="depends_on",
                        subject=subject,
                        object=property_match.group(2),
                        file=chunk.source,
                        line=line_number,
                        score=0,
                        evidence=line.strip(),
                    )
                )

            init_match = re.search(
                r"\binit\s*\(([^)]*)\)",
                line,
            )

            if init_match is None:
                continue

            for parameter_type in re.findall(
                r":\s*([A-Za-z_][A-Za-z0-9_.<>]*)",
                init_match.group(1),
            ):
                facts.append(
                    EvidenceFact(
                        kind="depends_on",
                        subject=subject,
                        object=parameter_type,
                        file=chunk.source,
                        line=line_number,
                        score=0,
                        evidence=line.strip(),
                    )
                )

        return facts

    def _extract_swift_calls(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        subject = chunk.qualified_symbol or chunk.symbol

        if subject is None:
            return []

        facts = []

        for line_number, line in self._iter_lines(chunk):
            for match in re.finditer(
                r"\b([A-Za-z_][A-Za-z0-9_]*)"
                r"\.([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                line,
            ):
                facts.append(
                    EvidenceFact(
                        kind="calls",
                        subject=subject,
                        object=(
                            f"{match.group(1)}."
                            f"{match.group(2)}"
                        ),
                        file=chunk.source,
                        line=line_number,
                        score=0,
                        evidence=line.strip(),
                    )
                )

        return facts

    def _extract_python_facts(
        self,
        chunk: CodeChunk,
    ) -> list[EvidenceFact]:

        if chunk.symbol_type != "ClassDef":
            return []

        bases = chunk.metadata.get("bases", [])

        return [
            self._fact(
                kind="inherits_or_conforms",
                subject=chunk.symbol or "",
                object=base,
                chunk=chunk,
                evidence=chunk.signature or "",
            )
            for base in bases
            if chunk.symbol
        ]

    def _fact(
        self,
        kind: str,
        subject: str,
        object: str,
        chunk: CodeChunk,
        evidence: str,
    ) -> EvidenceFact:

        return EvidenceFact(
            kind=kind,
            subject=subject,
            object=object,
            file=chunk.source,
            line=chunk.start_line,
            score=0,
            evidence=evidence.strip(),
        )

    def _iter_lines(
        self,
        chunk: CodeChunk,
    ):

        for offset, line in enumerate(
            chunk.content.splitlines()
        ):
            yield chunk.start_line + offset, line

    def _first_declaration_line(
        self,
        content: str,
    ) -> str:

        return content.split(
            "{",
            1,
        )[0].strip()

    def _split_swift_type_list(
        self,
        value: str,
    ) -> list[str]:

        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    def _deduplicate(
        self,
        facts: list[EvidenceFact],
    ) -> list[EvidenceFact]:

        unique = {}

        for fact in facts:
            key = (
                fact.kind,
                fact.subject,
                fact.object,
                fact.file,
            )

            unique.setdefault(key, fact)

        return list(unique.values())
