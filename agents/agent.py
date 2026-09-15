import json
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage

from domain.agent_state import AgentState
from domain.agent_status import AgentStatus
from context.context_manager import ContextManager
from domain.context import AgentContext

class Agent:

    def __init__(
        self,
        llm,
        context_manager: ContextManager,
        system_prompt: str,
        indexed_evidence: str | None = None,
    ):
        self.llm = llm
        self.context_manager = context_manager
        self.system_prompt = system_prompt
        self.indexed_evidence = indexed_evidence

    async def run(self, state: AgentState):

        iteration = state.iteration + 1

        context = await self.context_manager.build(state)

        prompt = self._create_prompt(context=context)

        response = await self.llm.invoke(prompt)

        messages = []

        for tool_call in response["tool_calls"]:

            tool_call_id = str(uuid4())

            messages.append(
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool_call["tool"],
                            "args": json.loads(
                                tool_call["arguments"]
                            ),
                            "id": tool_call_id,
                            "type": "tool_call",
                        }
                    ],
                )
            )

            messages.append(
                ToolMessage(
                    content=str(tool_call["result"]),
                    tool_call_id=tool_call_id,
                )
            )

        messages.append(
            AIMessage(
                content=response["content"],
            )
        )

        tool_history = [
            *state.tool_history,
            *response["tool_calls"],
        ]

        return {
            "status": AgentStatus.COMPLETED,
            "iteration": iteration,
            "messages": messages,
            "tool_calls": (
                state.tool_calls
                + len(response["tool_calls"])
            ),
            "tool_history": tool_history,
        }

    def _compact_tool_history(
        self,
        tool_history: list,
    ) -> str:

        if not tool_history:
            return "No previous tool calls."

        lines = []

        for index, tool_call in enumerate(
            tool_history[-5:],
            start=1,
        ):
            result = str(
                tool_call.get("result", "")
            )

            if len(result) > 800:
                result = result[:800] + "...[truncated]"

            lines.append(
                "\n".join(
                    [
                        f"{index}. Tool: {tool_call.get('tool')}",
                        f"Arguments: {tool_call.get('arguments')}",
                        f"Result excerpt: {result}",
                    ]
                )
            )

        return "\n\n".join(lines)

    def _create_prompt(self, context: AgentContext) -> str:
        skills = "\n".join(
            f"- {skill}"
            for skill in context.skills
        )

        rules = "\n".join(
            f"- {rule}"
            for rule in context.rules
        )

        indexed_evidence = (
            self.indexed_evidence
            or "No pre-retrieved repository evidence."
        )

        tools = "\n".join(
            f"- {tool.name}"
            for tool in context.tools
        )

        tool_history = self._compact_tool_history(
            context.tool_history
        )
        important_instructions = (
            "Use the indexed repository evidence above as the "
            "repository inspection result. Do not claim that "
            "repository search access is missing when indexed "
            "evidence is present. When the task asks for exact "
            "paths or symbols, cite the file and symbol metadata "
            "from the evidence verbatim. Do not replace concrete "
            "implementation symbols with broader protocol, parent, "
            "or assembler names. If a checklist item contains "
            "multiple symbols, preserve the concrete Default*, "
            "function, Repository, DataSource, UseCase, and "
            "ViewModel symbols that are relevant to the task."
            if self.indexed_evidence
            else (
                "Use only the repository tools listed above when "
                "repository evidence is required.\n\n"
                "Do not guess when the repository can be inspected."
            )
        )

        prompt = f"""
{self.system_prompt}

## Task

{context.task}

## Skills

{skills}

## Rules

{rules}

## Available repository tools

{tools}

## Indexed repository evidence

{indexed_evidence}

## Previous verification feedback

{context.verification_feedback}

## Tool history

{tool_history}

IMPORTANT:

{important_instructions}
"""
        return prompt
