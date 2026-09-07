import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from domain.agent_state import AgentState
from domain.agent_status import AgentStatus

from graph.agent_graph import create_agent_graph

from infrastructure.llm.copilot_llm import CopilotLLM
from infrastructure.evidence.evidence_packet_builder import (
    EvidencePacketBuilder,
)

from infrastructure.tools.search_code import search_code
from infrastructure.tools.read_file import read_file

from infrastructure.tools.copilot_tool_adapter import (
    to_copilot_tool,
)

from tests.agent_tasks import AGENT_TASKS


RESULTS_DIR = Path("benchmark_results")
MODE = os.environ.get(
    "BENCHMARK_MODE",
    "baseline",
)
ENABLE_LLM_VERIFICATION = False


def _status_value(status):

    return getattr(status, "value", str(status))


def _message_content(message):

    content = getattr(message, "content", "")

    if isinstance(content, str):
        return content

    return str(content)


def _final_answer(result: dict) -> str:

    messages = result.get("messages", [])

    if not messages:
        return ""

    return _message_content(messages[-1])


def _evaluate_answer(
    answer: str,
    expected: dict,
) -> dict:

    answer_lower = answer.lower()

    missing_mentions = [
        value
        for value in expected.get("must_mention", [])
        if value.lower() not in answer_lower
    ]

    missing_files = [
        value
        for value in expected.get("files", [])
        if value.lower() not in answer_lower
    ]

    missing_symbols = [
        value
        for value in expected.get("symbols", [])
        if value.lower() not in answer_lower
    ]

    return {
        "passed": not (
            missing_mentions
            or missing_files
            or missing_symbols
        ),
        "missing_mentions": missing_mentions,
        "missing_files": missing_files,
        "missing_symbols": missing_symbols,
    }


def _write_result(record: dict) -> None:

    RESULTS_DIR.mkdir(exist_ok=True)

    output_path = (
        RESULTS_DIR
        / f"{datetime.now(timezone.utc).date()}.jsonl"
    )

    with output_path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


async def main():

    for task_definition in AGENT_TASKS:
        tools = _tools_for_mode()
        llm = CopilotLLM(
            model="gpt-5.4",
            tools=tools,
        )

        await llm.start()

        try:
            if MODE == "evidence_packet":
                await _run_evidence_packet_task(
                    llm=llm,
                    task_definition=task_definition,
                )
            else:
                graph = create_agent_graph(
                    llm,
                    tools,
                    enable_verification=(
                        ENABLE_LLM_VERIFICATION
                    ),
                )

                await _run_task(
                    graph=graph,
                    llm=llm,
                    task_definition=task_definition,
                )

        finally:
            await llm.stop()


def _tools_for_mode():

    if MODE == "evidence_packet":
        return []

    copilot_search_code = to_copilot_tool(
        search_code
    )

    copilot_read_file = to_copilot_tool(
        read_file
    )

    return [
        copilot_search_code,
        copilot_read_file,
    ]


async def _run_evidence_packet_task(
    llm: CopilotLLM,
    task_definition: dict,
):

    print("\n")
    print("=" * 60)
    print(
        f"TASK: {task_definition['id']}"
    )
    print("=" * 60)

    builder = EvidencePacketBuilder(
        repository_path=".",
        top_k=6,
        top_facts=6,
    )
    evidence_packet = builder.build(
        task_definition["task"]
    )
    prompt = _build_evidence_prompt(
        task=task_definition["task"],
        evidence=evidence_packet.to_prompt_section(),
    )

    start = time.perf_counter()

    response = await llm.invoke(prompt)

    elapsed = (
        time.perf_counter() - start
    )
    usage = llm.get_usage()
    invocations = llm.get_invocations()
    answer = response["content"]
    evaluation = _evaluate_answer(
        answer=answer,
        expected=task_definition.get(
            "expected",
            {},
        ),
    )

    record = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "task_id": task_definition["id"],
        "category": task_definition.get(
            "category"
        ),
        "difficulty": task_definition.get(
            "difficulty"
        ),
        "mode": MODE,
        "llm_verification_enabled": False,
        "task": task_definition["task"],
        "expected": task_definition.get(
            "expected",
            {},
        ),
        "status": "COMPLETED",
        "passed": evaluation["passed"],
        "evaluation": evaluation,
        "latency_ms": int(elapsed * 1000),
        "iterations": 1,
        "tool_calls": 0,
        "usage": {
            "input_tokens": usage[
                "input_tokens"
            ],
            "output_tokens": usage[
                "output_tokens"
            ],
            "total_tokens": usage[
                "total_tokens"
            ],
            "cost": usage["cost"],
        },
        "evidence_packet": evidence_packet.to_dict(),
        "llm_invocations": invocations,
        "answer": answer,
        "tool_history": [],
    }

    _write_result(record)
    _print_result(
        usage=usage,
        invocations=invocations,
        status="COMPLETED",
        evaluation=evaluation,
        iterations=1,
        tool_calls=0,
        elapsed=elapsed,
        tool_history=[],
    )


def _build_evidence_prompt(
    task: str,
    evidence: str,
) -> str:

    return f"""
You are a software engineering assistant.

Answer the task using only the repository evidence provided.
If the evidence is insufficient, say exactly what is missing.

Task:
{task}

Repository evidence:
{evidence}

Answer format:
- Location
- Explanation
- Evidence
"""


async def _run_task(
    graph,
    llm: CopilotLLM,
    task_definition: dict,
):

    print("\n")
    print("=" * 60)
    print(
        f"TASK: {task_definition['id']}"
    )
    print("=" * 60)

    state = AgentState(
        status=AgentStatus.RUNNING,
        task=task_definition["task"],
    )

    start = time.perf_counter()

    result = await graph.ainvoke(
        state
    )

    elapsed = (
        time.perf_counter() - start
    )
    usage = llm.get_usage()
    invocations = llm.get_invocations()
    answer = _final_answer(result)
    evaluation = _evaluate_answer(
        answer=answer,
        expected=task_definition.get(
            "expected",
            {},
        ),
    )

    record = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "task_id": task_definition["id"],
        "category": task_definition.get(
            "category"
        ),
        "difficulty": task_definition.get(
            "difficulty"
        ),
        "mode": MODE,
        "llm_verification_enabled": (
            ENABLE_LLM_VERIFICATION
        ),
        "task": task_definition["task"],
        "expected": task_definition.get(
            "expected",
            {},
        ),
        "status": _status_value(
            result["status"]
        ),
        "passed": evaluation["passed"],
        "evaluation": evaluation,
        "latency_ms": int(elapsed * 1000),
        "iterations": result["iteration"],
        "tool_calls": result["tool_calls"],
        "usage": {
            "input_tokens": usage[
                "input_tokens"
            ],
            "output_tokens": usage[
                "output_tokens"
            ],
            "total_tokens": usage[
                "total_tokens"
            ],
            "cost": usage["cost"],
        },
        "llm_invocations": invocations,
        "answer": answer,
        "tool_history": result.get(
            "tool_history",
            [],
        ),
    }

    _write_result(record)

    _print_result(
        usage=usage,
        invocations=invocations,
        status=result["status"],
        evaluation=evaluation,
        iterations=result["iteration"],
        tool_calls=result["tool_calls"],
        elapsed=elapsed,
        tool_history=result.get(
            "tool_history",
            [],
        ),
    )


def _print_result(
    usage: dict,
    invocations: list,
    status,
    evaluation: dict,
    iterations: int,
    tool_calls: int,
    elapsed: float,
    tool_history: list,
):

    print("\nTOKENS:")
    print(f"Input:  {usage['input_tokens']}")
    print(f"Output: {usage['output_tokens']}")
    print(f"Total:  {usage['total_tokens']}")

    print("\nLLM INVOCATIONS:")
    for index, invocation in enumerate(
        invocations,
        start=1,
    ):
        print(f"\n--- INVOCATION {index} ---")
        print(
            "INPUT TOKENS: "
            f"{invocation['input']['tokens']}"
        )
        print("INPUT TEXT:")
        print(invocation["input"]["text"])
        print(
            "OUTPUT TOKENS: "
            f"{invocation['output']['tokens']}"
        )
        print("OUTPUT TEXT:")
        print(invocation["output"]["text"])

    print("\nSTATUS:")
    print(status)

    print("\nEVALUATION:")
    print(
        json.dumps(
            evaluation,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nITERATIONS:")
    print(iterations)

    print("\nTOOL CALLS:")
    print(tool_calls)

    print("\nTIME:")
    print(f"{elapsed:.2f}s")

    print("\nTOOL HISTORY:")
    for tool_call in tool_history:
        print(tool_call)


asyncio.run(main())