from __future__ import annotations

import argparse

from infrastructure.ingestion.vector.semantic_code_index import (
    SemanticCodeIndex,
)


def main() -> None:

    parser = argparse.ArgumentParser(
        description="Build and query the semantic code vector index.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    rebuild_parser = subparsers.add_parser(
        "rebuild",
        help="Index repository chunks into the vector database.",
    )
    rebuild_parser.add_argument(
        "repository_path",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Search an already built vector database.",
    )
    search_parser.add_argument(
        "repository_path",
    )
    search_parser.add_argument(
        "query",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )
    search_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild before searching.",
    )

    args = parser.parse_args()

    index = SemanticCodeIndex(
        repository_path=args.repository_path,
    )

    if args.command == "rebuild":
        chunks = index.rebuild()
        print(f"Indexed chunks: {len(chunks)}")
        print(f"Stored vectors: {index.count()}")
        return

    results = index.search(
        args.query,
        limit=args.limit,
        rebuild=args.rebuild,
    )

    print(f"Stored vectors: {index.count()}")

    for position, result in enumerate(
        results,
        start=1,
    ):
        chunk = result.chunk
        print(
            f"#{position} score={result.score:.4f} "
            f"file={chunk.source} "
            f"symbol={chunk.qualified_symbol or chunk.symbol}"
        )
        print(f"context={chunk.context_path}")
        print()


if __name__ == "__main__":
    main()
