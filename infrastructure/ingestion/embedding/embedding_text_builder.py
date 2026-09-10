from infrastructure.ingestion.chunking.code_chunk import (
    CodeChunk,
)


class EmbeddingTextBuilder:

    def build(self, chunk: CodeChunk) -> str:
        sections = [
            self._build_identity(chunk),
            self._build_context(chunk),
            self._build_code(chunk),
        ]

        return "\n\n".join(
            section
            for section in sections
            if section
        )

    def _build_identity(
        self,
        chunk: CodeChunk,
    ) -> str:

        lines = [
            f"Language: {chunk.language}",
        ]

        if chunk.symbol:
            lines.append(
                f"Symbol: {chunk.qualified_symbol or chunk.symbol}"
            )

        if chunk.symbol_type:
            lines.append(
                f"Symbol type: {chunk.symbol_type}"
            )

        if chunk.parent_symbol:
            lines.append(
                f"Parent: {chunk.parent_symbol}"
            )

        return "\n".join(lines)

    def _build_context(
        self,
        chunk: CodeChunk,
    ) -> str:

        metadata = chunk.metadata

        lines = []

        context_path = (
            chunk.context_path
            or metadata.get("context_path")
        )
        if context_path:
            lines.append(
                f"Context path: {context_path}"
            )

        module = metadata.get("module")
        if module:
            lines.append(
                f"Module: {module}"
            )

        imports = metadata.get("imports", [])
        if imports:
            lines.append(
                "Imports:\n"
                + "\n".join(imports)
            )

        modifiers = metadata.get("modifiers", [])
        if modifiers:
            lines.append(
                "Modifiers: "
                + ", ".join(modifiers)
            )

        extended_type = metadata.get("extended_type")
        if extended_type:
            lines.append(
                f"Extended type: {extended_type}"
            )

        if chunk.signature:
            lines.append(
                f"Signature:\n{chunk.signature}"
            )

        if not lines:
            return ""

        return "\n".join(lines)

    def _build_code(
        self,
        chunk: CodeChunk,
    ) -> str:

        return f"Code:\n{chunk.content}"