from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.evidence.source_indexer import (
    SourceIndexer,
)


def test_source_indexer_resolves_swift_module_from_xcodeproj():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_directory = _create_xcode_project(root)

        chunks = SourceIndexer().create_index(
            str(root)
        )

    assert _cashback_repository_module(chunks) == "Cashback"


def test_source_indexer_resolves_swift_module_when_indexing_subdirectory():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_directory = _create_xcode_project(root)

        chunks = SourceIndexer().create_index(
            str(source_directory)
        )

    assert _cashback_repository_module(chunks) == "Cashback"


def test_source_indexer_resolves_swift_package_module_from_sources_subdirectory():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_directory = _create_swift_package(root)

        chunks = SourceIndexer().create_index(
            str(source_directory)
        )

    assert _cashback_repository_module(chunks) == "Plans"


def test_source_indexer_distinguishes_swift_class_and_struct_types():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_directory = _create_swift_package(root)

        chunks = SourceIndexer().create_index(
            str(source_directory)
        )

    symbol_types = {
        chunk.symbol: chunk.symbol_type
        for chunk in chunks
        if chunk.language == "swift"
    }

    assert (
        symbol_types["CashbackRepositoryImpl"]
        == "class_declaration"
    )
    assert (
        symbol_types["DefaultPlansRepository"]
        == "struct_declaration"
    )


def test_source_indexer_uses_ast_for_large_swift_files_with_conflict_markers():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_directory = _create_conflicted_swift_package(root)

        chunks = SourceIndexer().create_index(
            str(source_directory)
        )

    symbol_types = {
        chunk.symbol: chunk.symbol_type
        for chunk in chunks
        if chunk.language == "swift"
    }

    assert (
        symbol_types["ContributionStringsProvider"]
        == "protocol_declaration"
    )
    assert (
        symbol_types["DefaultContributionStringsProvider"]
        == "struct_declaration"
    )
    assert all(
        chunk.symbol_type != "line"
        for chunk in chunks
        if chunk.language == "swift"
    )


def test_source_indexer_uses_file_chunk_for_large_swift_files():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_directory = _create_large_swift_package(root)

        chunks = SourceIndexer().create_index(
            str(source_directory)
        )

    swift_chunks = [
        chunk
        for chunk in chunks
        if chunk.language == "swift"
    ]

    assert len(swift_chunks) == 1
    assert swift_chunks[0].symbol == "LargeViewModel"
    assert swift_chunks[0].symbol_type == "file"
    assert swift_chunks[0].metadata["module"] == "Plans"
    assert "final class LargeViewModel" in swift_chunks[0].content


def test_source_indexer_keeps_protocol_methods_inside_protocol_chunk():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source_directory = _create_swift_package(root)

        chunks = SourceIndexer().create_index(
            str(source_directory)
        )

    provider_chunks = [
        chunk
        for chunk in chunks
        if chunk.language == "swift"
        and chunk.symbol == "PlansRepository"
    ]

    assert len(provider_chunks) == 1
    assert (
        provider_chunks[0].symbol_type
        == "protocol_declaration"
    )
    assert "func getPlans()" in provider_chunks[0].content
    assert all(
        chunk.symbol_type != "protocol_function_declaration"
        for chunk in chunks
    )


def _create_xcode_project(
    root: Path,
) -> Path:

    source_directory = root / "Sources"
    source_directory.mkdir()

    swift_file = (
        source_directory
        / "CashbackRepositoryImpl.swift"
    )
    swift_file.write_text(
        """
final class CashbackRepositoryImpl {
    func getCashback() {}
}

protocol PlansRepository {
    func getPlans()
}

struct DefaultPlansRepository {
    func getPlans() {}
}
""".strip(),
        encoding="utf-8",
    )

    xcodeproj = root / "MyApp.xcodeproj"
    xcodeproj.mkdir()
    (xcodeproj / "project.pbxproj").write_text(
        """
{
    objects = {
        111111111111111111111111 = {
            isa = PBXGroup;
            path = Sources;
            children = (
                222222222222222222222222,
            );
        };
        222222222222222222222222 = {
            isa = PBXFileReference;
            path = CashbackRepositoryImpl.swift;
            sourceTree = "<group>";
        };
        333333333333333333333333 = {
            isa = PBXBuildFile;
            fileRef = 222222222222222222222222 /* CashbackRepositoryImpl.swift */;
        };
        444444444444444444444444 = {
            isa = PBXSourcesBuildPhase;
            files = (
                333333333333333333333333 /* CashbackRepositoryImpl.swift */,
            );
        };
        555555555555555555555555 = {
            isa = PBXNativeTarget;
            name = Cashback;
            buildPhases = (
                444444444444444444444444 /* Sources */,
            );
        };
    };
}
""".strip(),
        encoding="utf-8",
    )

    return source_directory


def _create_swift_package(
    root: Path,
) -> Path:

    source_directory = root / "Sources" / "Plans"
    source_directory.mkdir(parents=True)

    swift_file = (
        source_directory
        / "CashbackRepositoryImpl.swift"
    )
    swift_file.write_text(
        """
final class CashbackRepositoryImpl {
    func getCashback() {}
}

protocol PlansRepository {
    func getPlans()
}

struct DefaultPlansRepository {
    func getPlans() {}
}
""".strip(),
        encoding="utf-8",
    )

    (root / "Package.swift").write_text(
        """
// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "Plans",
    products: [
        .library(name: "Plans", targets: ["Plans"])
    ],
    targets: [
        .target(
            name: "Plans"
        )
    ]
)
""".strip(),
        encoding="utf-8",
    )

    return root / "Sources"


def _create_large_swift_package(
    root: Path,
) -> Path:

    source_directory = root / "Sources" / "Plans"
    source_directory.mkdir(parents=True)

    padding = "\n".join(
        f"    func method{index}() -> String {{ \"{index}\" }}"
        for index in range(400)
    )

    swift_file = source_directory / "LargeViewModel.swift"
    swift_file.write_text(
        f"""
import Foundation

final class LargeViewModel {{
{padding}
}}
""".strip(),
        encoding="utf-8",
    )

    (root / "Package.swift").write_text(
        """
// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "Plans",
    targets: [
        .target(
            name: "Plans"
        )
    ]
)
""".strip(),
        encoding="utf-8",
    )

    return root / "Sources"


def _create_conflicted_swift_package(
    root: Path,
) -> Path:

    source_directory = root / "Sources" / "Plans"
    source_directory.mkdir(parents=True)

    padding = "\n".join(
        f"// padding {index}"
        for index in range(600)
    )

    swift_file = (
        source_directory
        / "ContributionStringsProvider.swift"
    )
    swift_file.write_text(
        f"""
// Copyright © 2026 CaixaBank. All rights reserved.

<<<<<<< HEAD
=======
import AppBaseApi
>>>>>>> branch
import Foundation

protocol ContributionStringsProvider: Sendable {{
    func amountOf(balance: String) -> String
}}

enum ContributionStringsProviderAssembler {{
    static func assemble() -> some ContributionStringsProvider {{
<<<<<<< HEAD
        return DefaultContributionStringsProvider()
=======
        DefaultContributionStringsProvider()
>>>>>>> branch
    }}
}}

struct DefaultContributionStringsProvider: ContributionStringsProvider {{
    func amountOf(balance: String) -> String {{
        return balance
    }}
}}

{padding}
""".strip(),
        encoding="utf-8",
    )

    (root / "Package.swift").write_text(
        """
// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "Plans",
    targets: [
        .target(
            name: "Plans"
        )
    ]
)
""".strip(),
        encoding="utf-8",
    )

    return root / "Sources"


def _cashback_repository_module(
    chunks: list,
) -> str | None:

    swift_chunks = [
        chunk
        for chunk in chunks
        if chunk.language == "swift"
        and chunk.symbol == "CashbackRepositoryImpl"
    ]

    assert swift_chunks
    return swift_chunks[0].metadata["module"]


if __name__ == "__main__":
    test_source_indexer_resolves_swift_module_from_xcodeproj()
    test_source_indexer_resolves_swift_module_when_indexing_subdirectory()
    test_source_indexer_resolves_swift_package_module_from_sources_subdirectory()
    test_source_indexer_distinguishes_swift_class_and_struct_types()
    test_source_indexer_uses_ast_for_large_swift_files_with_conflict_markers()
    test_source_indexer_uses_file_chunk_for_large_swift_files()
    test_source_indexer_keeps_protocol_methods_inside_protocol_chunk()
