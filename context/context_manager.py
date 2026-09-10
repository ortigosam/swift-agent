from domain.agent_state import AgentState
from domain.context import AgentContext

from context.message_selector import MessageSelector
from context.skill_selector import SkillSelector
from context.rule_selector import RuleSelector
from context.tool_selector import ToolSelector

class ContextManager:

    def __init__(
        self,
        tools,
    ):

        self.message_selector = MessageSelector()
        self.skill_selector = SkillSelector()
        self.rule_selector = RuleSelector()
        self.tool_selector = ToolSelector()
        self.tools = tools

    async def build(
        self,
        state: AgentState,
    ) -> AgentContext:

        skills = self.skill_selector.select(
            state.task
        )

        rules = self.rule_selector.select(
            state.task
        )

        messages = self.message_selector.select(
            messages=state.messages,
            token_budget=state.token_budget,
        )

        tools = self.tool_selector.select(
            task=state.task,
            tools=self.tools,
        )

        return AgentContext(
            task=state.task,
            skills=skills,
            rules=rules,
            plan=state.plan,
            rag_results=[],
            graph_results=[],
            messages=messages,
            tool_history=state.tool_history,
            verification_feedback=(
                state.verification_feedback
            ),
            tools=tools,
            token_budget=state.token_budget,
        )