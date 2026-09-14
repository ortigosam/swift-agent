from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


AGENT_TASKS = [
    {
        "id": "cashback_vector_retrieval",
        "category": "semantic_retrieval",
        "difficulty": "easy",
        "repository_path": str(PROJECT_ROOT / "examples" / "ios"),
        "task": (
            "Explain the getCashback dataSource call and mention "
            "the source file name."
        ),
        "expected": {
            "files": [
                "CashbackRepositoryImpl.swift",
            ],
            "symbols": [
                "getCashback",
            ],
            "must_mention": [
                "dataSource.getCashback",
            ],
        },
    }
]
