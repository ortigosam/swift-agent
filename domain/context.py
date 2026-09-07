from dataclasses import dataclass, field


@dataclass
class AgentContext:

    task: str = ""

    skills: list = field(
        default_factory=list
    )

    rules: list = field(
        default_factory=list
    )

    plan: list = field(
        default_factory=list
    )

    rag_results: list = field(
        default_factory=list
    )

    graph_results: list = field(
        default_factory=list
    )

    messages: list = field(
        default_factory=list
    )

    tool_history: list = field(
        default_factory=list
    )

    verification_feedback: str = ""

    tools: list = field(
        default_factory=list
    )

    token_budget: int = 8000