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

    context_path: str | None = None
    context_path_parts: list[str] = field(default_factory=list)
    file_path_parts: list[str] = field(default_factory=list)
    symbol_path: list[str] = field(default_factory=list)

    signature: str | None = None

    metadata: dict = field(default_factory=dict)