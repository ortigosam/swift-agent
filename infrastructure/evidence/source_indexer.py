import ast
import re
from pathlib import Path

from infrastructure.ingestion.chunking.ast_chunker import (
    ASTChunker,
)
from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)
from infrastructure.ingestion.module.composite_module_resolver import (
    CompositeModuleResolver,
)
from infrastructure.ingestion.module.null_module_resolver import (
    NullModuleResolver,
)
from infrastructure.ingestion.module.module_resolver import (
    ModuleResolver,
)
from infrastructure.ingestion.module.swift_package_module_resolver import (
    SwiftPackageModuleResolver,
)
from infrastructure.ingestion.module.xcode_module_resolver import (
    XcodeModuleResolver,
)
from infrastructure.ingestion.parser.swift_parser import (
    SwiftParser,
)


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    ".build",
    "__pycache__",
    "benchmark_results",
    "build",
    "dist",
    "Pods",
    "ADAM_ENT_FULL",
    "Readme",
    "Scripts",
    "LocalSpecs",
    "ADAM_ENT_FULLTests",
    "ADAM_FULL",
    ".gitlab",
    ".github"
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

MAX_SWIFT_AST_CHUNK_CHARS = 10_000


class _RepositoryRelativeModuleResolver(ModuleResolver):

    def __init__(
        self,
        repository_root: Path,
        delegate: ModuleResolver,
    ):
        self.repository_root = repository_root
        self.delegate = delegate

    def resolve(
        self,
        source_path: str,
    ) -> str | None:

        return self.delegate.resolve(
            str(self.repository_root / source_path)
        )


class SourceIndexer:

    def __init__(
        self,
        module_resolver: ModuleResolver | None = None,
    ):
        self.swift_parser = SwiftParser()
        self.module_resolver = module_resolver

    def create_index(
        self,
        repository_path: str,
    ) -> list[CodeChunk]:

        root = Path(repository_path).resolve()
        chunks: list[CodeChunk] = []
        swift_chunker = ASTChunker(
            module_resolver=(
                self.module_resolver
                or self._module_resolver_for(root)
            ),
        )

        for path in sorted(root.rglob("*")):
            if not self._should_index(path):
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                )
            except (OSError, UnicodeDecodeError) as error:
                print(f"SOURCE_INDEXER_ERROR: Could not read file {path}: {error}")
                continue

            source = str(
                path.relative_to(root)
            )

            if path.suffix == ".swift":
                swift_chunks = self._index_swift(
                    content=content,
                    source=source,
                    chunker=swift_chunker,
                )
                chunks.extend(swift_chunks)
                continue

            if path.suffix == ".py":
                chunks.extend(
                    self._index_python(
                        content=content,
                        source=source,
                    )
                )

            if path.suffix != ".py" and path.suffix != ".swift":
                print("ERROR LEYENDO UN FICHERO CON FORMATO NO DESEADO {path}")

            chunks.extend(
                self._index_lines(
                    content=content,
                    source=source,
                    language=self._language_for(path),
                )
            )

        return chunks

    def _module_resolver_for(
        self,
        root: Path,
    ) -> ModuleResolver:

        resolvers: list[ModuleResolver] = [
            *self._swift_package_resolvers_for(root),
        ]

        xcode_resolver = self._xcode_module_resolver_for(root)

        if xcode_resolver is not None:
            resolvers.append(xcode_resolver)

        resolvers.append(NullModuleResolver())

        return CompositeModuleResolver(resolvers)

    def _xcode_module_resolver_for(
        self,
        root: Path,
    ) -> ModuleResolver | None:

        xcodeproj_path = self._find_xcodeproj(root)

        if xcodeproj_path is None:
            return None

        try:
            resolver = XcodeModuleResolver(
                str(xcodeproj_path)
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            print(
                "SOURCE_INDEXER_ERROR: Could not load Xcode project "
                f"{xcodeproj_path}: {error}"
            )
            return None

        if not resolver.available:
            return None

        return _RepositoryRelativeModuleResolver(
            repository_root=root,
            delegate=resolver,
        )

    def _swift_package_resolvers_for(
        self,
        root: Path,
    ) -> list[ModuleResolver]:

        package_paths = self._find_package_swift_paths(root)
        resolvers: list[ModuleResolver] = []

        for package_path in package_paths:
            try:
                resolver = SwiftPackageModuleResolver(
                    str(package_path)
                )
            except (OSError, UnicodeDecodeError, ValueError) as error:
                print(
                    "SOURCE_INDEXER_ERROR: Could not load Swift package "
                    f"{package_path}: {error}"
                )
                continue

            if resolver.available:
                resolvers.append(
                    _RepositoryRelativeModuleResolver(
                        repository_root=root,
                        delegate=resolver,
                    )
                )

        return resolvers

    def _find_package_swift_paths(
        self,
        root: Path,
    ) -> list[Path]:

        candidates = [
            path
            for path in root.rglob("Package.swift")
            if path.is_file()
            and not self._is_ignored_path(path)
        ]

        for current in [
            root,
            *root.parents,
        ]:
            package_path = current / "Package.swift"

            if (
                package_path.is_file()
                and not self._is_ignored_path(package_path)
            ):
                candidates.append(package_path)

        return sorted(
            set(candidates),
            key=lambda path: (
                -len(path.parent.parts),
                path.as_posix(),
            ),
        )

    def _find_xcodeproj(
        self,
        root: Path,
    ) -> Path | None:

        candidates = self._find_xcodeproj_descendants(root)

        if candidates:
            return self._nearest_xcodeproj(
                candidates=candidates,
                base=root,
            )

        for ancestor in root.parents:
            candidates = self._find_xcodeproj_children(
                ancestor
            )

            if candidates:
                return self._nearest_xcodeproj(
                    candidates=candidates,
                    base=ancestor,
                )

        return None

    def _find_xcodeproj_descendants(
        self,
        root: Path,
    ) -> list[Path]:

        return [
            path
            for path in root.rglob("*.xcodeproj")
            if path.is_dir()
            and not self._is_ignored_path(path)
        ]

    def _find_xcodeproj_children(
        self,
        root: Path,
    ) -> list[Path]:

        try:
            return [
                path
                for path in root.glob("*.xcodeproj")
                if path.is_dir()
                and not self._is_ignored_path(path)
            ]
        except OSError:
            return []

    def _nearest_xcodeproj(
        self,
        candidates: list[Path],
        base: Path,
    ) -> Path:

        return sorted(
            candidates,
            key=lambda path: (
                len(path.relative_to(base).parts),
                path.relative_to(base).as_posix(),
            ),
        )[0]

    def _should_index(
        self,
        path: Path,
    ) -> bool:

        if not path.is_file():
            return False

        if path.suffix not in SUPPORTED_EXTENSIONS:
            return False

        return not self._is_ignored_path(path)

    def _is_ignored_path(
        self,
        path: Path,
    ) -> bool:

        return any(
            part in IGNORED_DIRECTORIES
            for part in path.parts
        )

    # Metodo que orquesta la indexacion en swift, parsea a ast el codigo y luego lo divide en chunks.
    def _index_swift(
        self,
        content: str,
        source: str,
        chunker: ASTChunker,
    ) -> list[CodeChunk]:

        if self._has_git_conflict_markers(content):
            chunks = self._index_conflicted_swift(
                content=content,
                source=source,
                chunker=chunker,
            )

            if chunks:
                return chunks

        if len(content) > MAX_SWIFT_AST_CHUNK_CHARS:
            return self._index_file(
                content=content,
                source=source,
                language="swift",
                module=chunker.module_resolver.resolve(source),
            )

        tree = self.swift_parser.parse(
            self._swift_parse_source(content)
        )

        chunks = chunker.chunk(
            tree=tree,
            source=content,
            source_path=source,
        )

        if chunks:
            return chunks

        return self._index_file(
            content=content,
            source=source,
            language="swift",
            module=chunker.module_resolver.resolve(source),
        )

    def _index_file(
        self,
        content: str,
        source: str,
        language: str,
        module: str | None = None,
    ) -> list[CodeChunk]:

        breadcrumb = self._breadcrumb_metadata(
            source=source,
            module=module,
            symbol_path=[
                Path(source).stem,
            ],
            current_label=(
                f"File symbol: {Path(source).stem}"
            ),
        )

        return [
            CodeChunk(
                content=content,
                source=source,
                start_line=1,
                end_line=max(
                    1,
                    len(content.splitlines()),
                ),
                language=language,
                symbol=Path(source).stem,
                qualified_symbol=Path(source).stem,
                symbol_type="file",
                context_path=breadcrumb["context_path"],
                context_path_parts=breadcrumb[
                    "context_path_parts"
                ],
                file_path_parts=breadcrumb["file_path_parts"],
                symbol_path=breadcrumb["symbol_path"],
                metadata={
                    "module": module,
                    "imports": self._source_imports(
                        content=content,
                        language=language,
                    ),
                    **breadcrumb,
                },
            )
        ]

    def _breadcrumb_metadata(
        self,
        source: str,
        module: str | None = None,
        symbol_path: list[str] | None = None,
        current_label: str | None = None,
    ) -> dict:

        context_path_parts = []

        if module:
            context_path_parts.append(
                f"Module: {module}"
            )

        context_path_parts.append(
            f"File: {source}"
        )

        if current_label:
            context_path_parts.append(current_label)

        return {
            "context_path": " > ".join(context_path_parts),
            "context_path_parts": context_path_parts,
            "file_path_parts": [
                part
                for part in source.split("/")
                if part
            ],
            "symbol_path": symbol_path or [],
        }

    def _source_imports(
        self,
        content: str,
        language: str,
    ) -> list[str]:

        if language != "swift":
            return []

        return [
            line.strip()
            for line in self._swift_parse_source(content).splitlines()
            if line.strip().startswith("import ")
        ]

    def _index_conflicted_swift(
        self,
        content: str,
        source: str,
        chunker: ASTChunker,
    ) -> list[CodeChunk]:

        parse_source = self._swift_parse_source(content)
        parse_lines = parse_source.splitlines()
        original_lines = content.splitlines()
        module = chunker.module_resolver.resolve(source)
        imports = [
            line.strip()
            for line in parse_lines
            if line.strip().startswith("import ")
        ]

        chunks = []

        for index, line in enumerate(
            parse_lines,
            start=1,
        ):
            match = re.match(
                r"\s*(?:@\w+(?:\([^)]*\))?\s*)*"
                r"(?:(?:public|private|package|internal|"
                r"fileprivate|open|final)\s+)*"
                r"(protocol|class|struct|enum|extension)\s+"
                r"([A-Za-z_][A-Za-z0-9_]*)",
                line,
            )

            if match is None:
                continue

            declaration_kind = match.group(1)
            symbol = match.group(2)
            context_symbol = (
                f"extension {symbol}"
                if declaration_kind == "extension"
                else symbol
            )
            end_line = self._swift_declaration_end_line(
                lines=parse_lines,
                start_line=index,
            )
            breadcrumb = self._breadcrumb_metadata(
                source=source,
                module=module,
                symbol_path=[context_symbol],
                current_label=(
                    f"Extension: {symbol}"
                    if declaration_kind == "extension"
                    else (
                        f"{declaration_kind.title()}: "
                        f"{symbol}"
                    )
                ),
            )

            chunks.append(
                CodeChunk(
                    content="\n".join(
                        original_lines[index - 1:end_line]
                    ),
                    source=source,
                    start_line=index,
                    end_line=end_line,
                    language="swift",
                    symbol=symbol,
                    qualified_symbol=context_symbol,
                    symbol_type=(
                        f"{declaration_kind}_declaration"
                    ),
                    context_path=breadcrumb["context_path"],
                    context_path_parts=breadcrumb[
                        "context_path_parts"
                    ],
                    file_path_parts=breadcrumb[
                        "file_path_parts"
                    ],
                    symbol_path=breadcrumb["symbol_path"],
                    metadata={
                        "module": module,
                        "imports": imports,
                        "modifiers": [],
                        "inherits_or_conforms": [],
                        "dependencies": [],
                        "calls": [],
                        **breadcrumb,
                    },
                )
            )

        return chunks

    def _swift_declaration_end_line(
        self,
        lines: list[str],
        start_line: int,
    ) -> int:

        depth = 0
        opened = False

        for index in range(start_line - 1, len(lines)):
            line = lines[index]
            depth += line.count("{")
            depth -= line.count("}")

            if "{" in line:
                opened = True

            if opened and depth <= 0:
                return index + 1

        return start_line

    def _has_git_conflict_markers(
        self,
        content: str,
    ) -> bool:

        return any(
            line.lstrip().startswith("<<<<<<<")
            for line in content.splitlines()
        )

    def _swift_parse_source(
        self,
        content: str,
    ) -> str:

        lines = []
        in_conflict = False
        keep_conflict_side = False

        for line in content.splitlines(
            keepends=True,
        ):
            stripped = line.lstrip()

            if stripped.startswith("<<<<<<<"):
                in_conflict = True
                keep_conflict_side = False
                lines.append(self._blank_source_line(line))
                continue

            if in_conflict and stripped.startswith("======="):
                keep_conflict_side = True
                lines.append(self._blank_source_line(line))
                continue

            if in_conflict and stripped.startswith(">>>>>>>"):
                in_conflict = False
                keep_conflict_side = False
                lines.append(self._blank_source_line(line))
                continue

            if in_conflict and not keep_conflict_side:
                lines.append(self._blank_source_line(line))
                continue

            lines.append(line)

        return "".join(lines)

    def _blank_source_line(
        self,
        line: str,
    ) -> str:

        newline = "\n" if line.endswith("\n") else ""

        return (
            " " * (len(line) - len(newline))
            + newline
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
            breadcrumb = self._breadcrumb_metadata(
                source=source,
                symbol_path=[node.name],
                current_label=(
                    f"{type(node).__name__}: "
                    f"{node.name}"
                ),
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
                    context_path=breadcrumb["context_path"],
                    context_path_parts=breadcrumb[
                        "context_path_parts"
                    ],
                    file_path_parts=breadcrumb[
                        "file_path_parts"
                    ],
                    symbol_path=breadcrumb["symbol_path"],
                    signature=self._python_signature(
                        node=node,
                        lines=lines,
                    ),
                    metadata={
                        "bases": self._python_bases(node),
                        **breadcrumb,
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

            breadcrumb = self._breadcrumb_metadata(
                source=source,
                current_label=f"Line: {line_number}",
            )

            chunks.append(
                CodeChunk(
                    content=line.strip(),
                    source=source,
                    start_line=line_number,
                    end_line=line_number,
                    language=language,
                    symbol=None,
                    symbol_type="line",
                    context_path=breadcrumb["context_path"],
                    context_path_parts=breadcrumb[
                        "context_path_parts"
                    ],
                    file_path_parts=breadcrumb[
                        "file_path_parts"
                    ],
                    symbol_path=breadcrumb["symbol_path"],
                    metadata=breadcrumb,
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
