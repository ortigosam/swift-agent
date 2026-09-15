import argparse
import asyncio
import importlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from domain.agent_state import AgentState
from domain.agent_status import AgentStatus

from infrastructure.llm.copilot_llm import CopilotLLM
from infrastructure.evidence.evidence_packet_builder import (
    EvidencePacketBuilder,
)

from infrastructure.tools.search_code import search_code
from infrastructure.tools.read_file import read_file

from infrastructure.tools.copilot_tool_adapter import (
    to_copilot_tool,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path(
    os.environ.get(
        "BENCHMARK_RESULTS_DIR",
        str(PROJECT_ROOT / "benchmark_results"),
    )
)
DEFAULT_LOGS_DIR = Path(
    os.environ.get(
        "BENCHMARK_LOGS_DIR",
        str(RESULTS_DIR / "logs"),
    )
)
DEFAULT_REPOSITORY_PATH = Path(
    os.environ.get(
        "BENCHMARK_REPOSITORY_PATH",
        ".",
    )
).expanduser().resolve()
DEFAULT_TASKS_MODULE = os.environ.get(
    "BENCHMARK_TASKS_MODULE",
    "tests.appima_agent_tasks",
)
DEFAULT_LLM_TIMEOUT_SECONDS = float(
    os.environ.get(
        "BENCHMARK_LLM_TIMEOUT_SECONDS",
        os.environ.get(
            "COPILOT_LLM_TIMEOUT_SECONDS",
            "900",
        ),
    )
)
DEFAULT_MODE = os.environ.get(
    "BENCHMARK_MODE",
    "baseline",
)
ENABLE_LLM_VERIFICATION = False
BASELINE_MODE = "baseline"
INDEXED_AGENT_MODE = "indexed_agent"
INDEXING_MODE = "evidence_packet"
VECTOR_INDEXING_MODE = "evidence_packet_vector"
DEFAULT_TOKEN_PRICES_USD_PER_1M = {
    "gpt-5-mini": {
        "input": 0.25,
        "output": 2.00,
    },
}
MODE_ALIASES = {
    "indexed": INDEXED_AGENT_MODE,
    "indexed-agent": INDEXED_AGENT_MODE,
    "indexing": INDEXING_MODE,
    "indexacion": INDEXING_MODE,
    "indexación": INDEXING_MODE,
    "vector": VECTOR_INDEXING_MODE,
    "vector-indexing": VECTOR_INDEXING_MODE,
    "evidence-vector": VECTOR_INDEXING_MODE,
}


def _status_value(status):

    return getattr(status, "value", str(status))


def _message_content(message):

    content = getattr(message, "content", "")

    if isinstance(content, str):
        return content

    return str(content)


def _estimated_token_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:

    input_price = os.environ.get(
        "BENCHMARK_INPUT_TOKEN_PRICE_USD_PER_1M"
    )
    output_price = os.environ.get(
        "BENCHMARK_OUTPUT_TOKEN_PRICE_USD_PER_1M"
    )

    if input_price is None or output_price is None:
        prices = DEFAULT_TOKEN_PRICES_USD_PER_1M.get(
            model,
            {
                "input": 0.0,
                "output": 0.0,
            },
        )
        input_price = input_price or str(prices["input"])
        output_price = output_price or str(prices["output"])

    return (
        (input_tokens / 1_000_000) * float(input_price)
        + (output_tokens / 1_000_000) * float(output_price)
    )


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

    RESULTS_DIR.mkdir(
        exist_ok=True,
        parents=True,
    )

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


class _FormattedStreamTee:

    def __init__(
        self,
        stream,
        log_file,
        stream_name: str,
    ):
        self._stream = stream
        self._log_file = log_file
        self._stream_name = stream_name
        self._buffer = ""
        self.encoding = getattr(
            stream,
            "encoding",
            "utf-8",
        )

    def write(
        self,
        text,
    ):

        if not isinstance(
            text,
            str,
        ):
            text = str(text)

        self._stream.write(text)
        self._buffer += text
        self._write_completed_lines()

        return len(text)

    def flush(
        self,
    ):

        self._stream.flush()
        self._log_file.flush()

    def flush_pending(
        self,
    ):

        if self._buffer:
            self._write_log_line(self._buffer)
            self._buffer = ""

        self.flush()

    def isatty(
        self,
    ):

        return self._stream.isatty()

    def fileno(
        self,
    ):

        return self._stream.fileno()

    def _write_completed_lines(
        self,
    ):

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split(
                "\n",
                1,
            )
            self._write_log_line(line)

    def _write_log_line(
        self,
        line: str,
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat(timespec="milliseconds")

        self._log_file.write(
            f"{timestamp} | {self._stream_name:<6} | {line}\n"
        )


class _BenchmarkOutputLogger:

    def __init__(
        self,
        path: Path,
    ):
        self.path = path
        self._file = None
        self._stdout = None
        self._stderr = None
        self._original_stdout = None
        self._original_stderr = None

    def __enter__(
        self,
    ):

        self.path.parent.mkdir(
            exist_ok=True,
            parents=True,
        )
        self._file = self.path.open(
            "a",
            encoding="utf-8",
            buffering=1,
        )
        self._write_header()

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout = _FormattedStreamTee(
            stream=sys.stdout,
            log_file=self._file,
            stream_name="STDOUT",
        )
        self._stderr = _FormattedStreamTee(
            stream=sys.stderr,
            log_file=self._file,
            stream_name="STDERR",
        )
        sys.stdout = self._stdout
        sys.stderr = self._stderr

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        exc_traceback,
    ):

        if self._stdout is not None:
            self._stdout.flush_pending()

        if self._stderr is not None:
            self._stderr.flush_pending()

        if exc_type is not None:
            self._write_exception(
                exc_type=exc_type,
                exc_value=exc_value,
                exc_traceback=exc_traceback,
            )

        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

        if self._file is not None:
            self._write_footer()
            self._file.close()

        return False

    def _write_header(
        self,
    ):

        started_at = datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds")

        self._file.write(
            "\n"
            + "=" * 100
            + "\n"
            + "BENCHMARK LOG\n"
            + f"Started at: {started_at}\n"
            + f"Command: {' '.join(sys.argv)}\n"
            + "=" * 100
            + "\n"
        )

    def _write_footer(
        self,
    ):

        finished_at = datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds")

        self._file.write(
            "=" * 100
            + "\n"
            + f"Finished at: {finished_at}\n"
            + "=" * 100
            + "\n"
        )

    def _write_exception(
        self,
        exc_type,
        exc_value,
        exc_traceback,
    ):

        self._file.write(
            "\n"
            + "-" * 100
            + "\n"
            + "UNHANDLED EXCEPTION\n"
            + "-" * 100
            + "\n"
        )

        for line in traceback.format_exception(
            exc_type,
            exc_value,
            exc_traceback,
        ):
            for formatted_line in line.rstrip().splitlines():
                self._file.write(
                    (
                        f"{datetime.now(timezone.utc).isoformat(timespec='milliseconds')} "
                        f"| ERROR  | {formatted_line}\n"
                    )
                )


def _resolve_log_path(
    log_file: Path | None,
) -> Path:

    configured_log_file = (
        log_file
        or (
            Path(os.environ["BENCHMARK_LOG_FILE"])
            if os.environ.get("BENCHMARK_LOG_FILE")
            else None
        )
    )

    if configured_log_file is not None:
        configured_log_file = configured_log_file.expanduser()

        if not configured_log_file.is_absolute():
            configured_log_file = PROJECT_ROOT / configured_log_file

        return configured_log_file

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d-%H%M%SZ")

    logs_dir = DEFAULT_LOGS_DIR.expanduser()

    if not logs_dir.is_absolute():
        logs_dir = PROJECT_ROOT / logs_dir

    return logs_dir / f"benchmark-{timestamp}.log"


async def main():

    args = _parse_args()

    with _BenchmarkOutputLogger(
        _resolve_log_path(args.log_file)
    ) as logger:
        print(f"BENCHMARK LOG FILE: {logger.path}")
        await _run_benchmark(args)


async def _run_benchmark(args):

    repository_path = args.repository_path.expanduser().resolve()
    modes = _benchmark_modes(args)
    task_definitions = _load_agent_tasks(args.tasks_module)
    task_definitions = _filter_agent_tasks(
        task_definitions=task_definitions,
        task_ids=args.task_id,
    )
    summary = []

    os.chdir(repository_path)
    print(f"BENCHMARK REPOSITORY: {repository_path}")
    print(f"BENCHMARK MODES: {', '.join(modes)}")
    print(f"BENCHMARK TASKS MODULE: {args.tasks_module}")
    print(f"BENCHMARK LLM TIMEOUT: {args.llm_timeout_seconds}s")
    print(f"BENCHMARK MODEL: {args.model}")
    print(
        "BENCHMARK VECTOR SEARCH: "
        f"{_vector_search_status(modes)}"
    )
    print(
        "BENCHMARK VECTOR DB: "
        f"{os.environ.get('SWIFT_AGENT_VECTOR_DB_PATH', 'default')}"
    )
    print(
        "BENCHMARK EMBEDDING MODEL: "
        f"{os.environ.get('SWIFT_AGENT_EMBEDDING_MODEL', 'default')}"
    )

    for mode in modes:
        print("\n")
        print("#" * 60)
        print(f"BENCHMARK RUN MODE: {mode}")
        print("#" * 60)

        for task_definition in task_definitions:
            task_repository_path = _repository_path_for_task(
                task_definition,
                repository_path,
            )
            os.chdir(task_repository_path)
            tools = _tools_for_mode(mode)
            llm = CopilotLLM(
                model=args.model,
                tools=tools,
                timeout_seconds=args.llm_timeout_seconds,
            )

            await llm.start()

            try:
                from graph.agent_graph import (
                    create_agent_graph,
                )

                with _vector_search_environment(mode):
                    indexed_evidence = _indexed_evidence_for_mode(
                        mode=mode,
                        repository_path=task_repository_path,
                        task=task_definition["task"],
                    )
                graph = create_agent_graph(
                    llm,
                    tools,
                    indexed_evidence=(
                        indexed_evidence.prompt_section
                        if indexed_evidence is not None
                        else None
                    ),
                    enable_verification=(
                        ENABLE_LLM_VERIFICATION
                    ),
                )

                record = await _run_task(
                    graph=graph,
                    llm=llm,
                    task_definition=task_definition,
                    repository_path=task_repository_path,
                    mode=mode,
                    indexed_evidence=indexed_evidence,
                )

                summary.append(record)

            finally:
                await llm.stop()

    _print_benchmark_summary(summary)


def _parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Run agent benchmark tasks in baseline mode, "
            "indexing/evidence-packet mode, or both."
        ),
    )
    parser.add_argument(
        "--repository-path",
        type=Path,
        default=DEFAULT_REPOSITORY_PATH,
        help=(
            "Repository or source path to benchmark. "
            "Defaults to BENCHMARK_REPOSITORY_PATH or '.'."
        ),
    )
    parser.add_argument(
        "--mode",
        default=DEFAULT_MODE,
        choices=[
            BASELINE_MODE,
            INDEXED_AGENT_MODE,
            INDEXING_MODE,
            VECTOR_INDEXING_MODE,
            "indexed",
            "indexed-agent",
            "indexing",
            "indexacion",
            "indexación",
            "vector",
            "vector-indexing",
            "evidence-vector",
        ],
        help=(
            "Benchmark mode to run. 'indexed_agent' uses the "
            "same agent as baseline with indexed evidence preloaded "
            "in the prompt. "
            "'indexing' is an alias for the same indexed agent flow "
            "using 'evidence_packet' as the mode name."
        ),
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help=(
            "Run baseline and indexed-agent modes "
            "sequentially for the same tasks."
        ),
    )
    parser.add_argument(
        "--compare-evidence-packet",
        action="store_true",
        help=(
            "Run baseline vs evidence_packet comparison. "
            "Both modes use the same Agent; evidence_packet also "
            "injects indexed evidence."
        ),
    )
    parser.add_argument(
        "--compare-rag",
        action="store_true",
        help=(
            "Run baseline, evidence_packet without embeddings, "
            "and evidence_packet_vector with embeddings."
        ),
    )
    parser.add_argument(
        "--tasks-module",
        default=DEFAULT_TASKS_MODULE,
        help=(
            "Python module containing AGENT_TASKS. Defaults to "
            "BENCHMARK_TASKS_MODULE or tests.appima_agent_tasks."
        ),
    )
    parser.add_argument(
        "--llm-timeout-seconds",
        type=float,
        default=DEFAULT_LLM_TIMEOUT_SECONDS,
        help="Timeout for each LLM invocation.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-mini",
        help="Model used by CopilotLLM.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=(
            "Path to the formatted benchmark log file. "
            "Defaults to BENCHMARK_LOG_FILE or "
            "benchmark_results/logs/benchmark-<timestamp>.log."
        ),
    )
    parser.add_argument(
        "--task-id",
        action="append",
        default=[],
        help=(
            "Run only the selected task id. Can be passed "
            "multiple times."
        ),
    )

    return parser.parse_args()


def _filter_agent_tasks(
    task_definitions: list[dict],
    task_ids: list[str],
) -> list[dict]:

    if not task_ids:
        return task_definitions

    selected = [
        task
        for task in task_definitions
        if task["id"] in set(task_ids)
    ]

    if not selected:
        raise ValueError(
            "No benchmark tasks matched --task-id values: "
            + ", ".join(task_ids)
        )

    return selected


def _benchmark_modes(args) -> list[str]:

    if args.compare_rag:
        return [
            BASELINE_MODE,
            INDEXING_MODE,
            VECTOR_INDEXING_MODE,
        ]

    if args.compare_evidence_packet:
        return [
            BASELINE_MODE,
            INDEXING_MODE,
        ]

    if args.compare:
        return [
            BASELINE_MODE,
            INDEXED_AGENT_MODE,
        ]

    return [
        _normalize_mode(args.mode),
    ]


def _normalize_mode(mode: str) -> str:

    return MODE_ALIASES.get(
        mode,
        mode,
    )


def _tools_for_mode(mode: str):

    if _uses_indexed_evidence(mode):
        return []

    copilot_search_code = to_copilot_tool(
        search_code
    )

    copilot_read_file = to_copilot_tool(
        read_file
    )
    tools = [
        copilot_search_code,
        copilot_read_file,
    ]

    return tools


class _IndexedEvidence:

    def __init__(
        self,
        prompt_section: str,
        packet,
        build_latency_ms: int,
    ):
        self.prompt_section = prompt_section
        self.packet = packet
        self.build_latency_ms = build_latency_ms


def _indexed_evidence_for_mode(
    mode: str,
    repository_path: Path,
    task: str,
):

    if not _uses_indexed_evidence(mode):
        return None

    builder = EvidencePacketBuilder(
        repository_path=str(repository_path),
        top_k=8,
        top_facts=8,
    )
    start = time.perf_counter()
    packet = builder.build(task)
    build_latency_ms = int(
        (time.perf_counter() - start) * 1000
    )

    return _IndexedEvidence(
        prompt_section=packet.to_prompt_section(
            max_chars_per_item=int(
                os.environ.get(
                    "BENCHMARK_MAX_CHARS_PER_EVIDENCE",
                    "800",
                )
            ),
        ),
        packet=packet,
        build_latency_ms=build_latency_ms,
    )


def _uses_indexed_evidence(mode: str) -> bool:

    return mode in {
        INDEXED_AGENT_MODE,
        INDEXING_MODE,
        VECTOR_INDEXING_MODE,
    }


def _effective_mode(mode: str) -> str:

    if mode == VECTOR_INDEXING_MODE:
        return INDEXING_MODE

    return mode


class _vector_search_environment:

    def __init__(
        self,
        mode: str,
    ):
        self.mode = mode
        self.previous = os.environ.get(
            "SWIFT_AGENT_VECTOR_SEARCH"
        )

    def __enter__(self):

        if self.mode == VECTOR_INDEXING_MODE:
            os.environ["SWIFT_AGENT_VECTOR_SEARCH"] = "1"
        elif self.mode == INDEXING_MODE:
            os.environ.pop(
                "SWIFT_AGENT_VECTOR_SEARCH",
                None,
            )

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):

        if self.previous is None:
            os.environ.pop(
                "SWIFT_AGENT_VECTOR_SEARCH",
                None,
            )
            return

        os.environ["SWIFT_AGENT_VECTOR_SEARCH"] = self.previous


def _mode_uses_vector_search(mode: str) -> bool:

    return mode == VECTOR_INDEXING_MODE


def _vector_search_status(modes: list[str]) -> str:

    if VECTOR_INDEXING_MODE in modes:
        return (
            "enabled for "
            f"{VECTOR_INDEXING_MODE}"
        )

    return os.environ.get(
        "SWIFT_AGENT_VECTOR_SEARCH",
        "",
    ) or "disabled"


def _load_agent_tasks(
    tasks_module: str,
) -> list[dict]:

    module = importlib.import_module(tasks_module)

    return module.AGENT_TASKS


def _repository_path_for_task(
    task_definition: dict,
    default_repository_path: Path,
) -> Path:

    task_repository_path = task_definition.get(
        "repository_path",
    )

    if not task_repository_path:
        return default_repository_path

    return Path(task_repository_path).expanduser().resolve()


async def _run_task(
    graph,
    llm: CopilotLLM,
    task_definition: dict,
    repository_path: Path,
    mode: str,
    indexed_evidence: _IndexedEvidence | None = None,
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

    if indexed_evidence is not None:
        print("\nINDEXED EVIDENCE:")
        print(
            "Build latency ms: "
            f"{indexed_evidence.build_latency_ms}"
        )
        print(
            "Facts: "
            f"{len(indexed_evidence.packet.facts)}"
        )
        print(
            "Items: "
            f"{len(indexed_evidence.packet.items)}"
        )

    result = await graph.ainvoke(
        state
    )

    elapsed = (
        time.perf_counter() - start
    )
    usage = llm.get_usage()
    invocations = llm.get_invocations()
    input_tokens = usage["input_tokens"]
    output_tokens = usage["output_tokens"]
    total_tokens = input_tokens + output_tokens
    estimated_token_cost = _estimated_token_cost(
        model=llm.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    evidence_build_latency_ms = (
        indexed_evidence.build_latency_ms
        if indexed_evidence is not None
        else 0
    )
    agent_latency_ms = int(elapsed * 1000)
    task_time_ms = (
        agent_latency_ms
        + evidence_build_latency_ms
    )
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
        "mode": mode,
        "repository_path": str(repository_path),
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
        "model": llm.model,
        "latency_ms": agent_latency_ms,
        "agent_latency_ms": agent_latency_ms,
        "task_time_ms": task_time_ms,
        "iterations": result["iteration"],
        "tool_calls": result["tool_calls"],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": estimated_token_cost,
            "estimated_cost": estimated_token_cost,
            "sdk_reported_cost": usage["cost"],
        },
        "evidence_packet": (
            indexed_evidence.packet.to_dict()
            if indexed_evidence is not None
            else None
        ),
        "indexed_evidence_build_latency_ms": (
            indexed_evidence.build_latency_ms
            if indexed_evidence is not None
            else None
        ),
        "vector_search_enabled": (
            _mode_uses_vector_search(mode)
        ),
        "vector_database_path": os.environ.get(
            "SWIFT_AGENT_VECTOR_DB_PATH"
        ),
        "embedding_model": os.environ.get(
            "SWIFT_AGENT_EMBEDDING_MODEL"
        ),
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

    return record


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


def _print_benchmark_summary(
    records: list[dict],
) -> None:

    if not records:
        return

    by_mode: dict[str, list[dict]] = {}

    for record in records:
        by_mode.setdefault(
            record["mode"],
            [],
        ).append(record)

    print("\n")
    print("=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(
        "mode | tasks | passed | avg_latency_ms | "
        "tokens | tool_calls | cost"
    )
    print("-" * 60)

    for mode, mode_records in by_mode.items():
        tasks = len(mode_records)
        passed = sum(
            1
            for record in mode_records
            if record["passed"]
        )
        avg_latency = int(
            sum(
                record["latency_ms"]
                for record in mode_records
            )
            / tasks
        )
        tokens = sum(
            record["usage"]["total_tokens"]
            for record in mode_records
        )
        tool_calls = sum(
            record["tool_calls"]
            for record in mode_records
        )
        cost = sum(
            record["usage"]["cost"]
            for record in mode_records
        )

        print(
            f"{mode} | {tasks} | {passed}/{tasks} | "
            f"{avg_latency} | {tokens} | {tool_calls} | "
            f"{cost:.6f}"
        )


if __name__ == "__main__":
    asyncio.run(main())