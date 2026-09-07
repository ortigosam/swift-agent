from pathlib import Path


class LanguageDetector:

    EXTENSION_TO_LANGUAGE = {
        ".swift": "swift",
        ".py": "python",
        ".java": "java",
        ".kt": "kotlin",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
    }

    def detect(
        self,
        file_path: str,
    ) -> str:

        extension = Path(
            file_path
        ).suffix.lower()

        return self.EXTENSION_TO_LANGUAGE.get(
            extension,
            "unknown",
        )