import asyncio

from domain.agent_state import AgentState
from domain.agent_status import AgentStatus

from graph.agent_graph import create_agent_graph

from infrastructure.llm.copilot_llm import CopilotLLM

from infrastructure.tools.search_code import search_code
from infrastructure.tools.read_file import read_file
from infrastructure.tools.copilot_tool_adapter import (
    to_copilot_tool,
)




async def main():

    # LangChain Tool → Copilot Tool
    copilot_search_code = to_copilot_tool(search_code)
    copilot_read_file = to_copilot_tool(read_file)
    tools = [copilot_search_code, copilot_read_file]
    
    # LLM
    llm = CopilotLLM(
        model="gpt-5.4",
        tools=tools,
    )

    await llm.start()

    try:

        # LangGraph
        agent_graph = create_agent_graph(llm, tools)

        # Initial state
        initial_state = AgentState(
            status=AgentStatus.RUNNING,
            task=(
                "Find where CashbackRepository is implemented "
                "in the repository."
            ),
        )

        # Execute graph
        result = await agent_graph.ainvoke(
            initial_state
        )

        print("\n=== FINAL STATE ===")
        print(result)

    finally:
        await llm.stop()


asyncio.run(main())
