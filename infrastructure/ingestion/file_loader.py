from pathlib import Path


class FileLoader:

    SUPPORTED_EXTENSIONS = {
        ".swift",
        ".py",
        ".java",
        ".kt",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
    }

    def load(
        self,
        repository_path: str,
    ) -> list[tuple[str, str]]:

        root = Path(repository_path)

        files = []

        for path in root.rglob("*"):

            if not path.is_file():
                continue

            if path.suffix not in self.SUPPORTED_EXTENSIONS:
                continue

            try:
                content = path.read_text(
                    encoding="utf-8"
                )
            except UnicodeDecodeError:
                continue

            files.append(
                (
                    str(path),
                    content,
                )
            )

        return files