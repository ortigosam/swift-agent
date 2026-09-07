from dataclasses import dataclass


@dataclass(frozen=True)
class FileContext:
    source_path: str
    module: str | None
    imports: list[str]