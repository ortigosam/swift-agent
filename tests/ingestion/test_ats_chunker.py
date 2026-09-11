import os
from pathlib import Path

from infrastructure.ingestion.parser.swift_parser import (
    SwiftParser,
)

from infrastructure.ingestion.chunking.ast_chunker import (
    ASTChunker,
)

from infrastructure.ingestion.module.xcode_module_resolver import (
    XcodeModuleResolver,
)

# Prueba el funcionamiento del ATSChunker y muestra que chunks devuelve para un archivo Swift específico

APPIMA_REPOSITORY_PATH = Path(
    os.environ.get(
        "APPIMA_REPOSITORY_PATH",
        "/Users/U01AE23C/projects/APPIMA",
    )
).expanduser().resolve()

PROJECT_PATH = (
    APPIMA_REPOSITORY_PATH
    / "APPIMA.xcodeproj"
)

SOURCE_PATH = (
    APPIMA_REPOSITORY_PATH
    / "APPIMA"
    / "Navigation"
    / "Deeplinks"
    / "AppDeepLinkAuthGuard.swift"
)


source = SOURCE_PATH.read_text(
    encoding="utf-8"
)


parser = SwiftParser()

tree = parser.parse(source)


module_resolver = XcodeModuleResolver(
    str(PROJECT_PATH),
)


chunker = ASTChunker(
    module_resolver=module_resolver,
)


chunks = chunker.chunk(
    tree=tree,
    source=source,
    source_path=str(SOURCE_PATH),
)

assert module_resolver.resolve(
    str(SOURCE_PATH)
) == "ADAM_ENT_FULL"

assert chunks

assert all(
    chunk.metadata.get("module") == "ADAM_ENT_FULL"
    for chunk in chunks
)


for chunk in chunks:

    print("\n====================")

    print("SYMBOL:", chunk.symbol)

    print("TYPE:", chunk.symbol_type)

    print("PARENT:", chunk.parent_symbol)

    print("QUALIFIED:", chunk.qualified_symbol)

    print(
        "LINES:",
        chunk.start_line,
        "-",
        chunk.end_line,
    )

    print("METADATA:", chunk.metadata)

    print("CONTEXT PATH:", chunk.context_path)

    print("====================")

    print(chunk.content)