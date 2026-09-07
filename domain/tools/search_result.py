from dataclasses import dataclass

@dataclass(frozen=True)
class SearchResult:
    file: str
    line: int
    snippet: str