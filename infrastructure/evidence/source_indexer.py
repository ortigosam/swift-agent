import ast
from pathlib import Path

from infrastructure.ingestion.chunking.ast_chunker import (
    ASTChunker,
)
from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)
from infrastructure.ingestion.module.null_module_resolver import (
    NullModuleResolver,
)
from infrastructure.ingestion.parser.swift_parser import (
    SwiftParser,
)


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "benchmark_results",
    "build",
    "dist",
}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".swift",
    ".java",
    ".kt",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}


class SourceIndexer:

    def __init__(self):
        self.swift_parser = SwiftParser()
        self.swift_chunker = ASTChunker(
            module_resolver=NullModuleResolver(),
        )

    def create_index(
        self,
        repository_path: str,
    ) -> list[CodeChunk]:

        root = Path(repository_path)
        chunks: list[CodeChunk] = []

        for path in sorted(root.rglob("*")):
            if not self._should_index(path):
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                )
            except (OSError, UnicodeDecodeError):
                continue

            source = str(
                path.relative_to(root)
            )

            if path.suffix == ".swift":
                chunks.extend(
                    self._index_swift(
                        content=content,
                        source=source,
                    )
                )
                continue

            if path.suffix == ".py":
                chunks.extend(
                    self._index_python(
                        content=content,
                        source=source,
                    )
                )

            chunks.extend(
                self._index_lines(
                    content=content,
                    source=source,
                    language=self._language_for(path),
                )
            )

        return chunks

    def _should_index(
        self,
        path: Path,
    ) -> bool:

        if not path.is_file():
            return False

        if path.suffix not in SUPPORTED_EXTENSIONS:
            return False

        return not any(
            part in IGNORED_DIRECTORIES
            for part in path.parts
        )

    def _index_swift(
        self,
        content: str,
        source: str,
    ) -> list[CodeChunk]:

        tree = self.swift_parser.parse(content)

        return self.swift_chunker.chunk(
            tree=tree,
            source=content,
            source_path=source,
        )

    def _index_python(
        self,
        content: str,
        source: str,
    ) -> list[CodeChunk]:

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        lines = content.splitlines()
        chunks = []

        for node in ast.walk(tree):
            if not isinstance(
                node,
                (
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue

            start_line = node.lineno
            end_line = getattr(
                node,
                "end_lineno",
                node.lineno,
            )

            chunks.append(
                CodeChunk(
                    content="\n".join(
                        lines[start_line - 1:end_line]
                    ),
                    source=source,
                    start_line=start_line,
                    end_line=end_line,
                    language="python",
                    symbol=node.name,
                    qualified_symbol=node.name,
                    symbol_type=type(node).__name__,
                    signature=self._python_signature(
                        node=node,
                        lines=lines,
                    ),
                    metadata={
                        "bases": self._python_bases(node),
                    },
                )
            )

        return chunks

    def _index_lines(
        self,
        content: str,
        source: str,
        language: str,
    ) -> list[CodeChunk]:

        chunks = []

        for line_number, line in enumerate(
            content.splitlines(),
            start=1,
        ):
            if not line.strip():
                continue

            chunks.append(
                CodeChunk(
                    content=line.strip(),
                    source=source,
                    start_line=line_number,
                    end_line=line_number,
                    language=language,
                    symbol=None,
                    symbol_type="line",
                )
            )

        return chunks

    def _python_signature(
        self,
        node,
        lines: list[str],
    ) -> str:

        return lines[node.lineno - 1].strip()

    def _python_bases(
        self,
        node,
    ) -> list[str]:

        if not isinstance(node, ast.ClassDef):
            return []

        bases = []

        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except (AttributeError, ValueError):
                continue

        return bases

    def _language_for(
        self,
        path: Path,
    ) -> str:

        return {
            ".py": "python",
            ".swift": "swift",
            ".java": "java",
            ".kt": "kotlin",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
        }.get(path.suffix, "unknown")
