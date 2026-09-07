from dataclasses import dataclass


@dataclass
class CodeChunk:

    content: str
    source: str
    start_line: int
    end_line: int


class CodeChunker:

    def __init__(
        self,
        chunk_size: int = 100,
        overlap: int = 20,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(
        self,
        content: str,
        source: str,
    ) -> list[CodeChunk]:

        lines = content.splitlines()

        chunks = []

        start = 0

        while start < len(lines):

            end = min(
                start + self.chunk_size,
                len(lines),
            )

            chunk_content = "\n".join(
                lines[start:end]
            )

            chunks.append(
                CodeChunk(
                    content=chunk_content,
                    source=source,
                    start_line=start + 1,
                    end_line=end,
                )
            )

            if end == len(lines):
                break

            start = end - self.overlap

        return chunks