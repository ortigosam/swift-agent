from infrastructure.ingestion.chunk import CodeChunk

class CodeSplitter:

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
        language: str,
    ) -> list[CodeChunk]:

        lines = content.splitlines()

        chunks = []

        start = 0

        while start < len(lines):

            end = min(
                start + self.chunk_size,
                len(lines),
            )

            chunk = CodeChunk(
                content="\n".join(
                    lines[start:end]
                ),
                source=source,
                start_line=start + 1,
                end_line=end,
                language=language,
            )

            chunks.append(chunk)

            if end == len(lines):
                break

            start = end - self.overlap

        return chunks