from infrastructure.ingestion.parser.swift_parser import (
    SwiftParser,
)

from infrastructure.ingestion.chunking.ast_chunker import (
    ASTChunker,
)

from infrastructure.ingestion.module.xcode_module_resolver import (
    XcodeModuleResolver,
)


source = """
protocol CashbackRepository {
    func getCashback() async throws -> Cashback
}

final class CashbackRepositoryImpl: CashbackRepository {

    private let dataSource: CashbackDataSource

    init(dataSource: CashbackDataSource) {
        self.dataSource = dataSource
    }

    func getCashback() async throws -> Cashback {
        try await dataSource.getCashback()
    }
}

extension CashbackRepositoryImpl {
    func getAdditionalCashback() async throws -> Cashback {
        try await dataSource.getAdditionalCashback()
    }
}
"""


parser = SwiftParser()

tree = parser.parse(source)


module_resolver = XcodeModuleResolver(
    "TuProyecto.xcodeproj",
)


chunker = ASTChunker(
    module_resolver=module_resolver,
)


chunks = chunker.chunk(
    tree=tree,
    source=source,
    source_path=(
        "Ruta/real/CashbackRepositoryImpl.swift"
    ),
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

    print("====================")

    print(chunk.content)