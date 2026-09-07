from domain.agent_state import AgentState, AgentStatus


class Verify:

    def __init__(self, llm):
        self.llm = llm

    async def run(self, state: AgentState):

        final_answer = self._final_answer(state)
        tool_summary = self._tool_summary(
            state.tool_history
        )

        prompt = f"""
You are an evaluator.

Determine whether the agent successfully completed the task.

Task:
{state.task}

Final answer:
{final_answer}

Repository evidence summary:
{tool_summary}

Evaluate the result carefully.

If the task was successfully completed, answer:

PASS

If the task was NOT successfully completed, answer:

FAIL: <explain exactly what is missing or wrong>

Do not suggest a completely new task.
Focus only on what the agent needs to improve.
"""

        response = await self.llm.invoke(prompt)

        result = response["content"].strip()

        if result.upper().startswith("PASS"):
            return {
                "status": AgentStatus.COMPLETED,
                "verification_feedback": "",
            }

        feedback = result

        return {
            "status": AgentStatus.FAILED,
            "verification_feedback": feedback,
        }

    def _final_answer(
        self,
        state: AgentState,
    ) -> str:

        if not state.messages:
            return ""

        content = getattr(
            state.messages[-1],
            "content",
            "",
        )

        if isinstance(content, str):
            return content

        return str(content)

    def _tool_summary(
        self,
        tool_history: list,
    ) -> str:

        if not tool_history:
            return "No tools were used."

        lines = []

        for index, tool_call in enumerate(
            tool_history,
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