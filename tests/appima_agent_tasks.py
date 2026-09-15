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
    {
        "id": "appima_login_flow_trace",
        "category": "dependency_tracing",
        "difficulty": "hard",
        "repository_path": str(APPIMA_REPOSITORY_PATH),
        "task": (
            "Analyze the APPIMA login flow from LoginViewModel.login "
            "until the first external networking calls. Trace every "
            "internal APPIMA call through the use case, repository, "
            "remote data source, crypto provider usage, and local "
            "storage side effects. Include exact file paths and symbol "
            "names, and stop network tracing at api.request."
        ),
        "expected": {
            "files": [
                (
                    "Features/Authentication/Sources/Authentication/"
                    "Features/Login/Presentation/LoginViewModel.swift"
                ),
                (
                    "Features/Authentication/Sources/Authentication/"
                    "Features/Login/Domain/UseCases/DoLoginUseCase/"
                    "DoLoginUseCase.swift"
                ),
                (
                    "Features/Authentication/Sources/Authentication/"
                    "Features/Login/Data/Repositories/LoginRepository/"
                    "LoginRepository.swift"
                ),
                (
                    "Features/Authentication/Sources/Authentication/"
                    "Features/Login/Data/DataSources/"
                    "LoginRemoteDataSource.swift"
                ),
            ],
            "symbols": [
                "LoginViewModel",
                "login",
                "DefaultDoLoginUseCase",
                "callAsFunction",
                "DefaultLoginRepository",
                "fetchSeed",
                "beginLogin",
                "completeLogin",
                "DefaultLoginRemoteDataSource",
                "getSeed",
                "loginResult",
                "getUserData",
            ],
            "must_mention": [
                "LoginViewModel",
                "doLoginUseCase",
                "DefaultDoLoginUseCase",
                "DefaultLoginRepository",
                "DefaultLoginRemoteDataSource",
                "fetchSeed",
                "beginLogin",
                "completeLogin",
                "encryptCredentials",
                "calculateOTP",
                "keyValueStorageRepository.save",
                "api.request",
            ],
        },
    },
    {
        "id": "appima_contribution_amount_flow_trace",
        "category": "dependency_tracing",
        "difficulty": "hard",
        "repository_path": str(APPIMA_REPOSITORY_PATH),
        "task": (
            "Analyze the ContributionAmountViewModel flow in APPIMA. "
            "Trace both load() and confirmAmount() through every "
            "internal APPIMA call until each path reaches the external "
            "networking boundary. Explain how contribution data, "
            "promotions, simulation, cache-independent repository calls, "
            "tracking, and navigation are connected. Include exact file "
            "paths and symbol names, and stop network tracing at "
            "api.request."
        ),
        "expected": {
            "files": [
                (
                    "Features/Plans/Sources/Plans/Features/"
                    "Contribution/Presentation/Views/"
                    "ContributionAmountView/"
                    "ContributionAmountViewModel.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Features/"
                    "Contribution/Domain/UseCases/"
                    "GetContributionDataUseCase/"
                    "GetContributionDataUseCase.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Features/"
                    "Contribution/Domain/UseCases/"
                    "GetPromotionsUseCase/GetPromotionsUseCase.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Features/"
                    "Contribution/Domain/UseCases/"
                    "SimulateContributionUseCase/"
                    "SimulateContributionUseCase.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Features/"
                    "Contribution/Data/Repositories/"
                    "ContributionRepository/"
                    "ContributionRepository.swift"
                ),
                (
                    "Features/Plans/Sources/Plans/Shared/Data/"
                    "DataSources/PlansRemoteDataSource/"
                    "PlansRemoteDataSource.swift"
                ),
            ],
            "symbols": [
                "ContributionAmountViewModel",
                "load",
                "confirmAmount",
                "DefaultGetContributionDataUseCase",
                "DefaultGetPromotionsUseCase",
                "DefaultSimulateContributionUseCase",
                "DefaultContributionRepository",
                "getContributionData",
                "getPromotions",
                "simulateContribution",
                "DefaultPlansRemoteDataSource",
                "fetchContributionData",
                "fetchPromotions",
                "simulateContribution",
            ],
            "must_mention": [
                "ContributionAmountViewModel",
                "load",
                "confirmAmount",
                "DefaultGetContributionDataUseCase",
                "DefaultGetPromotionsUseCase",
                "DefaultSimulateContributionUseCase",
                "DefaultContributionRepository",
                "DefaultPlansRemoteDataSource",
                "fetchContributionData",
                "fetchPromotions",
                "simulateContribution",
                "trackAmountView",
                "navigation",
                "api.request",
            ],
        },
    },
]
