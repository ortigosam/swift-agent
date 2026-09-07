from dataclasses import dataclass, field

from domain.agent_status import AgentStatus

@dataclass
class AgentState:

    status: AgentStatus = AgentStatus.START

    task: str = ""

    iteration: int = 0
    max_iterations: int = 3

    tool_calls: int = 0
    max_tool_calls: int = 20

    token_budget: int = 8000

    tool_history: list = field(default_factory=list)

    messages: list = field(default_factory=list)

    plan: list = field(default_factory=list)

    artifacts: dict = field(default_factory=dict)

    verification_feedback: str = ""