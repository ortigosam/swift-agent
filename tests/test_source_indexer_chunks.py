"""
Inspecciona todos los chunks que genera SourceIndexer para un
repositorio real.

Uso:

    uv run python -m tests.test_source_indexer_chunks /ruta/al/repo

Filtros opcionales:

    --language swift          Solo chunks de un lenguaje concreto.
    --symbol-type function_declaration
                               Solo chunks de un symbol_type concreto.
    --symbols-only             Descarta los chunks "line" (sin símbolo),
                                para ver solo clases/funciones/etc.
    --contains Cashback         Solo chunks cuyo contenido o símbolo
                                contenga este texto (no distingue mayúsculas).
    --limit 50                  Corta la salida a los N primeros chunks
                                (por defecto no hay límite).
"""

import argparse

from infrastructure.evidence.source_indexer import (
    SourceIndexer,
)
from contextlib import redirect_stdout



def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Indexa un repositorio con SourceIndexer y "
            "muestra todos los chunks generados."
        ),
    )

    parser.add_argument(
        "repository_path",
        help="Ruta al directorio del repositorio a indexar.",
    )

    parser.add_argument(
        "--language",
        default=None,
        help="Filtra por lenguaje (swift, python, javascript...).",
    )

    parser.add_argument(
        "--symbol-type",
        default=None,
        help=(
            "Filtra por symbol_type exacto "
            "(class_declaration, function_declaration, line...)."
        ),
    )

    parser.add_argument(
        "--symbols-only",
        action="store_true",
        help="Descarta los chunks sin símbolo (symbol_type == 'line').",
    )

    parser.add_argument(
        "--contains",
        default=None,
        help=(
            "Solo muestra chunks cuyo símbolo o contenido "
            "contenga este texto (sin distinguir mayúsculas)."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Número máximo de chunks a mostrar.",
    )

    return parser.parse_args()


def matches_filters(chunk, args) -> bool:

    if args.language and chunk.language != args.language:
        return False

    if args.symbol_type and chunk.symbol_type != args.symbol_type:
        return False

    if args.symbols_only and chunk.symbol_type == "line":
        return False

    if args.contains:
        needle = args.contains.lower()

        haystack = " ".join(
            value
            for value in [
                chunk.symbol or "",
                chunk.qualified_symbol or "",
                chunk.content,
            ]
        ).lower()

        if needle not in haystack:
            return False

    return True


def print_summary(chunks: list) -> None:

    by_language: dict[str, int] = {}
    by_symbol_type: dict[str, int] = {}

    for chunk in chunks:
        by_language[chunk.language] = (
            by_language.get(chunk.language, 0) + 1
        )
        by_symbol_type[chunk.symbol_type] = (
            by_symbol_type.get(chunk.symbol_type, 0) + 1
        )

    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Total chunks: {len(chunks)}")

    print("\nPor lenguaje:")
    for language, count in sorted(
        by_language.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {language}: {count}")

    print("\nPor symbol_type:")
    for symbol_type, count in sorted(
        by_symbol_type.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {symbol_type}: {count}")

    print("=" * 60)


def print_chunk(index: int, chunk) -> None:

    print("\n" + "-" * 60)
    print(f"CHUNK #{index}")
    print("FILE:", chunk.source)
    print("SYMBOL:", chunk.symbol)
    print("QUALIFIED:", chunk.qualified_symbol)
    print("TYPE:", chunk.symbol_type)
    print("PARENT:", chunk.parent_symbol)
    print("LANGUAGE:", chunk.language)
    print(
        "LINES:",
        chunk.start_line,
        "-",
        chunk.end_line,
    )

    if chunk.signature:
        print("SIGNATURE:", chunk.signature)

    if chunk.metadata:
        print("METADATA:", chunk.metadata)

    print("-" * 60)
    print(chunk.content)


def main() -> None:

    args = parse_args()

    with open("index_output.txt", "w", encoding="utf-8") as file:
        with redirect_stdout(file):

            indexer = SourceIndexer()

            print(f"Indexando: {args.repository_path}")

            chunks = indexer.create_index(
                args.repository_path
            )

            print_summary(chunks)

            filtered_chunks = [
                chunk
                for chunk in chunks
                if matches_filters(chunk, args)
            ]

            if args.limit is not None:
                filtered_chunks = filtered_chunks[: args.limit]

            print(
                f"\nMostrando {len(filtered_chunks)} "
                f"de {len(chunks)} chunks totales.\n"
            )

            for index, chunk in enumerate(
                filtered_chunks,
                start=1,
            ):
                print_chunk(index, chunk)


if __name__ == "__main__":
    main()
