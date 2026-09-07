from dataclasses import dataclass, field


@dataclass
class CodeChunk:
    content: str
    source: str

    start_line: int
    end_line: int

    language: str

    symbol: str | None = None
    qualified_symbol: str | None = None
    symbol_type: str | None = None
    parent_symbol: str | None = None

    signature: str | None = None

    metadata: dict = field(default_factory=dict)