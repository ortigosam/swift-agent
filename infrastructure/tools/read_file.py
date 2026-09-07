# infrastructure/tools/read_file.py

from pathlib import Path

from langchain_core.tools import tool


@tool
def read_file(
    path: str,
) -> str:
    """Read a source code file and return its content with line numbers."""

    file_path = Path(path)

    if not file_path.exists():
        return f"File not found: {path}"

    if not file_path.is_file():
        return f"Path is not a file: {path}"

    try:
        content = file_path.read_text(
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        return f"Unable to decode file as UTF-8: {path}"
    except OSError as error:
        return f"Unable to read file {path}: {error}"

    lines = content.splitlines()

    return "\n".join(
        f"{index} | {line}"
        for index, line in enumerate(lines, start=1)
    )