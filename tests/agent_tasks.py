AGENT_TASKS = [
    {
        "id": "EmbeddingModel_implementation",
        "category": "symbol_lookup",
        "difficulty": "easy",
        "task": (
            "Find where EmbeddingModel is implemented "
            "in the repository."
        ),
        "expected": {
            "files": [
                "infrastructure/embeddings/embedding_model.py",
                "infrastructure/embeddings/bedrock_embedding_model.py",
            ],
            "symbols": [
                "EmbeddingModel",
                "BedrockEmbeddingModel",
            ],
            "must_mention": [
                "EmbeddingModel",
                "BedrockEmbeddingModel",
            ],
        },
    },
    {
        "id": "cashback_data_source",
        "category": "architecture_question",
        "difficulty": "medium",
        "task": (
            "Find which class is responsible for obtaining "
            "cashback data."
        ),
        "expected": {
            "files": [],
            "symbols": [
                "CashbackDataSource",
            ],
            "must_mention": [
                "CashbackDataSource",
            ],
        },
    },
    {
        "id": "repository_dependency",
        "category": "dependency_tracing",
        "difficulty": "medium",
        "task": (
            "Find which classes depend on CashbackDataSource."
        ),
        "expected": {
            "files": [],
            "symbols": [
                "CashbackDataSource",
            ],
            "must_mention": [
                "CashbackDataSource",
            ],
        },
    },
    {
        "id": "cashback_method",
        "category": "method_explanation",
        "difficulty": "medium",
        "task": (
            "Find where getCashback is implemented and "
            "explain what it does."
        ),
        "expected": {
            "files": [],
            "symbols": [
                "getCashback",
            ],
            "must_mention": [
                "getCashback",
            ],
        },
    },
]