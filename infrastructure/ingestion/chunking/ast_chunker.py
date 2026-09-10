import re

from tree_sitter import Node

from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)
from infrastructure.ingestion.chunking.file_context import (
    FileContext,
)
from infrastructure.ingestion.module.module_resolver import (
    ModuleResolver,
)


class ASTChunker:

    CHUNKABLE_NODES = {
        "protocol_declaration",
        "class_declaration",
        "struct_declaration",
        "enum_declaration",
        "extension_declaration",
        "function_declaration",
        "init_declaration",
    }

    def __init__(
        self,
        module_resolver: ModuleResolver,
    ):
        self.module_resolver = module_resolver

    def chunk(
        self,
        tree,
        source: str,
        source_path: str,
    ) -> list[CodeChunk]:

        source_bytes = source.encode("utf-8")

        module = self.module_resolver.resolve(
            source_path
        )

        file_context = self._extract_file_context(
            root_node=tree.root_node,
            source_bytes=source_bytes,
            source_path=source_path,
            module=module,
        )
        line_count = len(source.splitlines())

        chunks: list[CodeChunk] = []

        self._visit(
            node=tree.root_node,
            source_bytes=source_bytes,
            chunks=chunks,
            symbol_stack=[],
            file_context=file_context,
            line_count=line_count,
        )

        return chunks

    # ------------------------------------------------------------------
    # AST traversal
    # ------------------------------------------------------------------

    def _visit(
        self,
        node: Node,
        source_bytes: bytes,
        chunks: list[CodeChunk],
        symbol_stack: list[str],
        file_context: FileContext,
        line_count: int,
    ) -> None:

        if node.type in self.CHUNKABLE_NODES:
            start_row = int(node.start_point.row)
            end_row = int(node.end_point.row)

            if not (
                0 <= start_row <= end_row <= line_count
            ):
                for child in node.children:
                    self._visit(
                        node=child,
                        source_bytes=source_bytes,
                        chunks=chunks,
                        symbol_stack=symbol_stack,
                        file_context=file_context,
                        line_count=line_count,
                    )

                return

            chunk = self._create_chunk(
                node=node,
                source_bytes=source_bytes,
                symbol_stack=symbol_stack,
                file_context=file_context,
            )

            chunks.append(chunk)

            next_symbol_stack = symbol_stack

            if chunk.symbol:
                next_symbol_stack = [
                    *symbol_stack,
                    chunk.symbol,
                ]

            for child in node.children:
                self._visit(
                    node=child,
                    source_bytes=source_bytes,
                    chunks=chunks,
                    symbol_stack=next_symbol_stack,
                    file_context=file_context,
                    line_count=line_count,
                )

            return

        for child in node.children:
            self._visit(
                node=child,
                source_bytes=source_bytes,
                chunks=chunks,
                symbol_stack=symbol_stack,
                file_context=file_context,
                line_count=line_count,
            )

    # ------------------------------------------------------------------
    # Chunk creation
    # ------------------------------------------------------------------

    def _create_chunk(
        self,
        node: Node,
        source_bytes: bytes,
        symbol_stack: list[str],
        file_context: FileContext,
    ) -> CodeChunk:

        content = self._get_source(
            node=node,
            source_bytes=source_bytes,
        )

        symbol = self._extract_symbol(
            node=node,
            source_bytes=source_bytes,
        )

        qualified_symbol = self._build_qualified_symbol(
            symbol=symbol,
            symbol_stack=symbol_stack,
        )

        parent_symbol = self._get_parent_symbol(
            symbol_stack=symbol_stack,
        )

        signature = self._extract_signature(
            node=node,
            source_bytes=source_bytes,
        )

        metadata = self._build_metadata(
            node=node,
            source_bytes=source_bytes,
            file_context=file_context,
        )

        return CodeChunk(
            content=content,
            source=file_context.source_path,
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1,
            language="swift",
            symbol=symbol,
            qualified_symbol=qualified_symbol,
            symbol_type=self._symbol_type(
                node=node,
                content=content,
            ),
            parent_symbol=parent_symbol,
            signature=signature,
            metadata=metadata,
        )

    def _symbol_type(
        self,
        node: Node,
        content: str,
    ) -> str:

        if node.type != "class_declaration":
            return node.type

        declaration_keyword = self._declaration_keyword(content)

        if declaration_keyword in {
            "class",
            "struct",
        }:
            return f"{declaration_keyword}_declaration"

        return node.type

    def _declaration_keyword(
        self,
        content: str,
    ) -> str | None:

        match = re.search(
            r"\b(class|struct)\b",
            content,
        )

        if match is None:
            return None

        return match.group(1)

    # ------------------------------------------------------------------
    # Source extraction
    # ------------------------------------------------------------------

    def _get_source(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> str:

        lines = source_bytes.splitlines(
            keepends=True,
        )

        if not self._has_valid_line_range(
            node=node,
            line_count=len(lines),
        ):
            return ""

        start_offset = self._offset_for_point(
            lines=lines,
            row=node.start_point.row,
            column=node.start_point.column,
        )
        end_offset = self._offset_for_point(
            lines=lines,
            row=node.end_point.row,
            column=node.end_point.column,
        )

        return source_bytes[
            start_offset:end_offset
        ].decode("utf-8")

    def _has_valid_line_range(
        self,
        node: Node,
        line_count: int,
    ) -> bool:

        start_row = int(node.start_point.row)
        end_row = int(node.end_point.row)

        return (
            0 <= start_row <= end_row <= line_count
        )

    def _offset_for_point(
        self,
        lines: list[bytes],
        row: int,
        column: int,
    ) -> int:

        if row >= len(lines):
            return sum(len(line) for line in lines)

        return sum(
            len(line)
            for line in lines[:row]
        ) + column

    # ------------------------------------------------------------------
    # Symbols
    # ------------------------------------------------------------------

    def _extract_symbol(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> str | None:

        if node.type == "init_declaration":
            return "init"

        if (
            node.type == "extension_declaration"
            or self._is_extension_declaration(node)
        ):
            return self._extract_extension_symbol(
                node=node,
                source_bytes=source_bytes,
            )

        for child in node.children:

            if child.type in {
                "type_identifier",
                "simple_identifier",
            }:
                return self._get_source(
                    node=child,
                    source_bytes=source_bytes,
                )

        return None

    def _extract_extension_symbol(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> str | None:

        for child in node.children:

            if child.type == "user_type":
                return self._extract_type_identifier(
                    node=child,
                    source_bytes=source_bytes,
                )

        return None

    def _extract_type_identifier(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> str | None:

        if node.type == "type_identifier":
            return self._get_source(
                node=node,
                source_bytes=source_bytes,
            )

        for child in node.children:

            result = self._extract_type_identifier(
                node=child,
                source_bytes=source_bytes,
            )

            if result:
                return result

        return None

    # ------------------------------------------------------------------
    # Qualified symbols
    # ------------------------------------------------------------------

    def _build_qualified_symbol(
        self,
        symbol: str | None,
        symbol_stack: list[str],
    ) -> str | None:

        if symbol is None:
            return None

        if not symbol_stack:
            return symbol

        return ".".join(
            [
                *symbol_stack,
                symbol,
            ]
        )

    def _get_parent_symbol(
        self,
        symbol_stack: list[str],
    ) -> str | None:

        if not symbol_stack:
            return None

        return ".".join(symbol_stack)

    # ------------------------------------------------------------------
    # Signatures
    # ------------------------------------------------------------------

    def _extract_signature(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> str | None:

        if node.type not in {
            "function_declaration",
            "protocol_function_declaration",
            "init_declaration",
        }:
            return None

        content = self._get_source(
            node=node,
            source_bytes=source_bytes,
        )

        if "{" in content:
            return content.split(
                "{",
                1,
            )[0].strip()

        return content.strip()

    # ------------------------------------------------------------------
    # File context
    # ------------------------------------------------------------------

    def _extract_file_context(
        self,
        root_node: Node,
        source_bytes: bytes,
        source_path: str,
        module: str | None,
    ) -> FileContext:

        imports = []

        for child in root_node.children:

            if child.type == "import_declaration":

                imports.append(
                    self._get_source(
                        node=child,
                        source_bytes=source_bytes,
                    ).strip()
                )

        return FileContext(
            source_path=source_path,
            module=module,
            imports=imports,
        )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _build_metadata(
        self,
        node: Node,
        source_bytes: bytes,
        file_context: FileContext,
    ) -> dict:

        metadata = {
            "module": file_context.module,
            "imports": file_context.imports,
            "modifiers": self._extract_modifiers(
                node=node,
                source_bytes=source_bytes,
            ),
            "inherits_or_conforms": (
                self._extract_inherited_types(
                    node=node,
                    source_bytes=source_bytes,
                )
            ),
            "dependencies": self._extract_dependencies(
                node=node,
                source_bytes=source_bytes,
            ),
            "calls": self._extract_calls(
                node=node,
                source_bytes=source_bytes,
            ),
        }

        if (
            node.type == "extension_declaration"
            or self._is_extension_declaration(node)
        ):

            metadata["extended_type"] = (
                self._extract_extension_symbol(
                    node=node,
                    source_bytes=source_bytes,
                )
            )

        return metadata

    def _is_extension_declaration(
        self,
        node: Node,
    ) -> bool:

        return any(
            child.type == "extension"
            for child in node.children
        )

    def _extract_inherited_types(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> list[dict]:

        inherited_types = []

        for child in node.children:
            if child.type != "inheritance_specifier":
                continue

            for inherited_type in self._find_nodes(
                node=child,
                node_type="user_type",
            ):
                type_name = self._extract_type_identifier(
                    node=inherited_type,
                    source_bytes=source_bytes,
                )

                if type_name:
                    inherited_types.append(
                        {
                            "type": type_name,
                            "line": inherited_type.start_point.row + 1,
                            "evidence": self._get_source(
                                node=child,
                                source_bytes=source_bytes,
                            ).strip(),
                        }
                    )

        return inherited_types

    def _extract_dependencies(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> list[dict]:

        dependencies = []

        for property_node in self._find_nodes(
            node=node,
            node_type="property_declaration",
        ):
            dependency = self._extract_property_dependency(
                node=property_node,
                source_bytes=source_bytes,
            )

            if dependency is not None:
                dependencies.append(dependency)

        for init_node in self._find_nodes(
            node=node,
            node_type="init_declaration",
        ):
            dependencies.extend(
                self._extract_init_dependencies(
                    node=init_node,
                    source_bytes=source_bytes,
                )
            )

        return dependencies

    def _extract_property_dependency(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> dict | None:

        name = None
        type_name = None

        for child in node.children:
            if child.type == "pattern":
                name = self._first_identifier(
                    node=child,
                    source_bytes=source_bytes,
                )

            if child.type == "type_annotation":
                type_name = self._first_user_type(
                    node=child,
                    source_bytes=source_bytes,
                )

        if name is None or type_name is None:
            return None

        return {
            "name": name,
            "type": type_name,
            "line": node.start_point.row + 1,
            "evidence": self._get_source(
                node=node,
                source_bytes=source_bytes,
            ).strip(),
        }

    def _extract_init_dependencies(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> list[dict]:

        dependencies = []

        for parameter in self._find_nodes(
            node=node,
            node_type="parameter",
        ):
            name = self._first_identifier(
                node=parameter,
                source_bytes=source_bytes,
            )
            type_name = self._first_user_type(
                node=parameter,
                source_bytes=source_bytes,
            )

            if name is None or type_name is None:
                continue

            dependencies.append(
                {
                    "name": name,
                    "type": type_name,
                    "line": parameter.start_point.row + 1,
                    "evidence": self._get_source(
                        node=parameter,
                        source_bytes=source_bytes,
                    ).strip(),
                }
            )

        return dependencies

    def _extract_calls(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> list[dict]:

        calls = []

        for call_node in self._find_nodes(
            node=node,
            node_type="call_expression",
        ):
            call = self._extract_navigation_call(
                node=call_node,
                source_bytes=source_bytes,
            )

            if call is not None:
                calls.append(call)

        return calls

    def _extract_navigation_call(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> dict | None:

        navigation = next(
            (
                child
                for child in node.children
                if child.type == "navigation_expression"
            ),
            None,
        )

        if navigation is None:
            return None

        identifiers = [
            self._get_source(
                node=identifier,
                source_bytes=source_bytes,
            )
            for identifier in self._find_nodes(
                node=navigation,
                node_type="simple_identifier",
            )
        ]

        if len(identifiers) < 2:
            return None

        target = ".".join(identifiers)

        return {
            "target": target,
            "line": node.start_point.row + 1,
            "evidence": self._get_source(
                node=node,
                source_bytes=source_bytes,
            ).strip(),
        }

    def _first_identifier(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> str | None:

        for identifier in self._find_nodes(
            node=node,
            node_type="simple_identifier",
        ):
            return self._get_source(
                node=identifier,
                source_bytes=source_bytes,
            )

        return None

    def _first_user_type(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> str | None:

        for user_type in self._find_nodes(
            node=node,
            node_type="user_type",
        ):
            return self._extract_type_identifier(
                node=user_type,
                source_bytes=source_bytes,
            )

        return None

    def _find_nodes(
        self,
        node: Node,
        node_type: str,
    ) -> list[Node]:

        matches = []

        if node.type == node_type:
            matches.append(node)

        for child in node.children:
            matches.extend(
                self._find_nodes(
                    node=child,
                    node_type=node_type,
                )
            )

        return matches

    def _extract_modifiers(
        self,
        node: Node,
        source_bytes: bytes,
    ) -> list[str]:

        modifiers = []

        for child in node.children:

            if child.type != "modifiers":
                continue

            for modifier in child.children:

                modifier_source = self._get_source(
                    node=modifier,
                    source_bytes=source_bytes,
                ).strip()

                if modifier_source:
                    modifiers.append(
                        modifier_source
                    )

        return modifiers