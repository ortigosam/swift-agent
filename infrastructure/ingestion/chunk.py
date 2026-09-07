from dataclasses import dataclass, field


@dataclass
class CodeChunk:

    content: str

    source: str

    start_line: int

    end_line: int

    language: str

    metadata: dict = field(
        default_factory=dict
    )