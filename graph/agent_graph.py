from context.context_manager import ContextManager
from langgraph.graph import StateGraph, START, END
from domain.agent_status import AgentStatus
from agents.agent import Agent
from domain.agent_state import AgentState
from graph.verify import Verify


def create_agent_graph(
    llm,
    tools,
    enable_verification: bool = True,
):

    agent = Agent(
        llm=llm,
        context_manager=ContextManager(tools=tools),
        system_prompt=(
            "You are a iOS software engineering agent. "
            "Analyze the task and provide a useful response."
        ),
    )

    builder = StateGraph(AgentState)

    verify = Verify(llm)

    builder.add_node("agent", agent.run)

    builder.add_edge(START, "agent")

    if not enable_verification:
        builder.add_edge("agent", END)

        return builder.compile()

    builder.add_node("verify", verify.run)

    builder.add_edge("agent", "verify")
    builder.add_conditional_edges("verify", route_after_verify,{
        "end": END,
        "retry": "agent",
        "failed": END,
    })

    return builder.compile()

def route_after_verify(state: AgentState):

    if state.status == AgentStatus.COMPLETED:
        return "end"

    if state.iteration < state.max_iterations:
        return "retry"

    return "failed"