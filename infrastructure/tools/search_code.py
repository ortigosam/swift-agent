import re
from pathlib import Path

from langchain_core.tools import tool

from domain.tools.search_result import SearchResult


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    ".build",
    "__pycache__",
    "benchmark_results",
    "build",
    "dist",
    "Pods",
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
    ".md",
    ".toml",
    ".yaml",
    ".yml",
}

MAX_RESULTS = 100


@tool
def search_code(query: str) -> list[dict]:
    """Search source code in the repository."""

    if not query.strip():
        return []

    root = Path.cwd()
    pattern = re.compile(query, re.IGNORECASE)

    results: list[SearchResult] = []

    for path in root.rglob("*"):
        if len(results) >= MAX_RESULTS:
            break

        if not path.is_file():
            continue

        if path.suffix not in SUPPORTED_EXTENSIONS:
            continue

        if any(
            part in IGNORED_DIRECTORIES
            for part in path.parts
        ):
            continue

        try:
            lines = path.read_text(
                encoding="utf-8",
            ).splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_number, line in enumerate(
            lines,
            start=1,
        ):
            if len(results) >= MAX_RESULTS:
                break

            if pattern.search(line) is None:
                continue

            results.append(
                SearchResult(
                    file=str(
                        path.relative_to(root)
                    ),
                    line=line_number,
                    snippet=line.strip(),
                )
            )

    return [
        {
            "file": result.file,
            "line": result.line,
            "snippet": result.snippet,
        }
        for result in results
    ]