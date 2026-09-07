from infrastructure.ingestion.file_loader import (
    FileLoader,
)

from infrastructure.ingestion.language_detector import (
    LanguageDetector,
)

from infrastructure.ingestion.code_splitter import (
    CodeSplitter,
)


class Indexer:

    def __init__(
        self,
        file_loader: FileLoader,
        language_detector: LanguageDetector,
        code_splitter: CodeSplitter,
    ):

        self.file_loader = file_loader
        self.language_detector = language_detector
        self.code_splitter = code_splitter

    def create_chunks(
        self,
        repository_path: str,
    ):

        files = self.file_loader.load(
            repository_path
        )

        chunks = []

        for file_path, content in files:

            language = self.language_detector.detect(
                file_path
            )

            file_chunks = self.code_splitter.split(
                content=content,
                source=file_path,
                language=language,
            )

            chunks.extend(file_chunks)

        return chunks