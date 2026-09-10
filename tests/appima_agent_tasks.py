import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPIMA_REPOSITORY_PATH = Path(
    os.environ.get(
        "APPIMA_REPOSITORY_PATH",
        "/Users/U01AE23C/projects/APPIMA",
    )
).expanduser().resolve()


AGENT_TASKS = [
    {
        "id": "EmbeddingModel_implementation",
        "category": "symbol_lookup",
        "difficulty": "easy",
        "repository_path": str(APPIMA_REPOSITORY_PATH),
        "task": (
            "Find where EmbeddingModel is implemented "
            "in the repository."
        ),
        "expected": {
            "files": [],
            "symbols": [],
            "must_mention": [],
        },
    },
    {
        "id": "appima_deeplinks_manager",
        "category": "architecture_question",
        "difficulty": "medium",
        "repository_path": str(APPIMA_REPOSITORY_PATH),
        "task": (
            "Find where deeplinks are handled in APPIMA and explain "
            "how authentication is enforced before dispatching a "
            "deeplink. Include exact file paths and symbol names."
        ),
        "expected": {
            "files": [
                "APPIMA/Navigation/AppCoordinator.swift",
                "APPIMA/Navigation/Deeplinks/DeepLinkHandlerAssembler.swift",
                "APPIMA/Navigation/Deeplinks/AppDeepLinkAuthGuard.swift",
            ],
            "symbols": [
                "DefaultAppCoordinator",
                "handleDeeplink",
                "DeepLinkHandlerAssembler",
                "AppDeepLinkAuthGuard",
            ],
            "must_mention": [
                "DefaultAppCoordinator",
                "handleDeeplink",
                "DeepLinkHandlerAssembler",
                "AppDeepLinkAuthGuard",
                "requiresAuth",
            ],
        },
    },
    {
        "id": "appima_plans_viewmodel_trace",
        "category": "dependency_tracing",
        "difficulty": "medium",
        "repository_path": str(APPIMA_REPOSITORY_PATH),
        "task": (
            "Analyze the PlansViewModel load flow and trace every "
            "internal APPIMA call until the chain reaches an external "
            "library call. Explain the full path as "
            "ViewModel function -> UseCase -> Repository -> DataSource, "
            "and stop when the next call is outside APPIMA. Include exact "
            "file paths and symbol names."
        ),
        "expected": {
            "files": [
                (
                    "Features/Plans/Sources/Plans/Features/"
                    "PlansOverview/Presentation/Views/PlansView/"
                    "PlansViewModel.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Features/"
                    "PlansOverview/Domain/UseCases/GetPlansUseCase/"
                    "GetPlansUseCase.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Shared/Data/"
                    "Repositories/PlansRepository/PlansRepository.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Shared/Data/"
                    "DataSources/PlansRemoteDataSource/"
                    "PlansRemoteDataSource.swift"
                ),
            ],
            "symbols": [
                "PlansViewModel",
                "load",
                "DefaultGetPlansUseCase",
                "callAsFunction",
                "DefaultPlansRepository",
                "getPlans",
                "DefaultPlansRemoteDataSource",
                "fetchPlans",
            ],
            "must_mention": [
                "PlansViewModel",
                "getPlansUseCase",
                "DefaultGetPlansUseCase",
                "DefaultPlansRepository",
                "PlansCacheDataSource",
                "DefaultPlansRemoteDataSource",
                "api.request",
            ],
        },
    },
]
