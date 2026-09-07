from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvidenceItem:
    file: str
    start_line: int
    end_line: int
    score: int
    content: str
    language: str
    symbol: str | None = None
    symbol_type: str | None = None
    signature: str | None = None


@dataclass(frozen=True)
class EvidenceFact:
    kind: str
    subject: str
    object: str
    file: str
    line: int
    score: int
    evidence: str

    def to_prompt_line(self) -> str:

        return (
            f"- {self.kind}: {self.subject} -> "
            f"{self.object} "
            f"({self.file}:{self.line}) "
            f"Evidence: {self.evidence}"
        )


@dataclass(frozen=True)
class EvidencePacket:
    query: str
    items: list[EvidenceItem]
    facts: list[EvidenceFact]

    def to_dict(self) -> dict:

        return {
            "query": self.query,
            "items": [
                asdict(item)
                for item in self.items
            ],
            "facts": [
                asdict(fact)
                for fact in self.facts
            ],
        }

    def to_prompt_section(
        self,
        max_chars_per_item: int = 500,
    ) -> str:

        if not self.items and not self.facts:
            return "No repository evidence was found."

        sections = []

        if self.facts:
            sections.append(
                "\n".join(
                    [
                        "## Repository facts",
                        *[
                            fact.to_prompt_line()
                            for fact in self.facts
                        ],
                    ]
                )
            )

        for index, item in enumerate(
            self.items,
            start=1,
        ):
            content = item.content.strip()

            if len(content) > max_chars_per_item:
                content = (
                    content[:max_chars_per_item]
                    + "\n...[truncated]"
                )

            metadata = [
                f"File: {item.file}",
                (
                    "Lines: "
                    f"{item.start_line}-{item.end_line}"
                ),
                f"Score: {item.score}",
                f"Language: {item.language}",
            ]

            if item.symbol:
                metadata.append(
                    f"Symbol: {item.symbol}"
                )

            if item.symbol_type:
                metadata.append(
                    f"Symbol type: {item.symbol_type}"
                )

            if item.signature:
                metadata.append(
                    f"Signature: {item.signature}"
                )

            sections.append(
                "\n".join(
                    [
                        f"## Evidence {index}",
                        *metadata,
                        "Content:",
                        content,
                    ]
                )
            )

        return "\n\n".join(sections)
