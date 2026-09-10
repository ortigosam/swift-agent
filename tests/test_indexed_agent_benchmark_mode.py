from pathlib import Path

from agents.agent import Agent
from domain.context import AgentContext
from tests.run_agent_benchmark import (
    BASELINE_MODE,
    INDEXED_AGENT_MODE,
    INDEXING_MODE,
    _indexed_evidence_for_mode,
    _tools_for_mode,
    _uses_indexed_evidence,
)
from tests.appima_agent_tasks import AGENT_TASKS


def test_indexed_agent_preloads_evidence_instead_of_retrieval_tool():
    tools = _tools_for_mode(INDEXED_AGENT_MODE)

    assert "retrieve_evidence" not in [
        tool.name
        for tool in tools
    ]


def test_evidence_packet_mode_uses_same_agent_tools():
    tool_names = [
        tool.name
        for tool in _tools_for_mode(INDEXING_MODE)
    ]

    assert tool_names == [
        "search_code",
        "read_file",
    ]


def test_indexed_modes_preload_indexed_evidence():
    assert not _uses_indexed_evidence(BASELINE_MODE)
    assert _uses_indexed_evidence(INDEXED_AGENT_MODE)
    assert _uses_indexed_evidence(INDEXING_MODE)


def test_appima_tasks_define_source_repository_path():
    appima_tasks = [
        task
        for task in AGENT_TASKS
        if task["id"].startswith("appima_")
    ]

    assert appima_tasks
    assert all(
        "repository_path" in task
        and "APPIMA" in task["repository_path"]
        for task in appima_tasks
    )


def test_baseline_does_not_preload_indexed_evidence():
    assert (
        _indexed_evidence_for_mode(
            mode=BASELINE_MODE,
            repository_path=Path("."),
            task="Find Example",
        )
        is None
    )


def test_agent_prompt_includes_preloaded_indexed_evidence():
    prompt = Agent(
        llm=None,
        context_manager=None,
        system_prompt="System prompt",
        indexed_evidence=(
            "## Evidence 1\n"
            "File: Example.swift\n"
            "Content:\n"
            "final class Example {}"
        ),
    )._create_prompt(
        AgentContext(
            task="Find Example",
            tools=[],
        )
    )

    assert "## Indexed repository evidence" in prompt
    assert "## Evidence 1" in prompt
    assert "Example.swift" in prompt


def test_agent_prompt_marks_missing_preloaded_indexed_evidence():
    prompt = Agent(
        llm=None,
        context_manager=None,
        system_prompt="System prompt",
    )._create_prompt(
        AgentContext(
            task="Find Example",
            tools=[],
        )
    )

    assert "## Indexed repository evidence" in prompt
    assert "No pre-retrieved repository evidence." in prompt


if __name__ == "__main__":
    test_indexed_agent_preloads_evidence_instead_of_retrieval_tool()
    test_evidence_packet_mode_uses_same_agent_tools()
    test_indexed_modes_preload_indexed_evidence()
    test_appima_tasks_define_source_repository_path()
    test_baseline_does_not_preload_indexed_evidence()
    test_agent_prompt_includes_preloaded_indexed_evidence()
    test_agent_prompt_marks_missing_preloaded_indexed_evidence()
