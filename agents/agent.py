import json
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage

from domain.agent_state import AgentState
from domain.agent_status import AgentStatus


class Agent:

    def __init__(
        self,
        llm,
        context_manager,
        system_prompt: str,
    ):
        self.llm = llm
        self.context_manager = context_manager
        self.system_prompt = system_prompt

    async def run(self, state: AgentState):

        iteration = state.iteration + 1

        context = await self.context_manager.build(state)

        skills = "\n".join(
            f"- {skill}"
            for skill in context.skills
        )

        rules = "\n".join(
            f"- {rule}"
            for rule in context.rules
        )

        rag = "\n".join(
            f"- {result.content}"
            for result in context.rag_results
        ) 

        tools = "\n".join(
            f"- {tool.name}"
            for tool in context.tools
        )

        tool_history = self._compact_tool_history(
            context.tool_history
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

## Retrieved knowledge

{rag}

## Previous verification feedback

{context.verification_feedback}

## Tool history

{tool_history}

IMPORTANT:

Use only the repository tools listed above when repository
evidence is required.

Do not guess when the repository can be inspected.
"""

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
            "status": AgentStatus.RUNNING,
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