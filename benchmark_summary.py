import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    args = parse_args()
    records = load_records(args.jsonl)

    if args.repository_path:
        records = [
            record
            for record in records
            if record.get("repository_path") == args.repository_path
        ]

    if not records:
        print("No benchmark records found.")
        return

    print(f"# Benchmark summary: `{args.jsonl}`")
    print()
    print(f"Records: {len(records)}")
    print()
    print_aggregate_table(records)
    print()
    print_task_table(records)

    comparison_rows = comparison_table_rows(records)

    if comparison_rows:
        print()
        print_comparison_table(comparison_rows)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Create markdown summary tables from a benchmark JSONL file."
        ),
    )
    parser.add_argument(
        "jsonl",
        type=Path,
        help="Path to benchmark_results/*.jsonl",
    )
    parser.add_argument(
        "--repository-path",
        help="Optional exact repository_path filter.",
    )

    return parser.parse_args()


def load_records(path: Path) -> list[dict]:
    records = []

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {error}"
                ) from error

    return records


def print_aggregate_table(records: list[dict]) -> None:
    print("## Aggregate by mode")
    print()
    print(
        "| Mode | Tasks | Passed | Pass rate | "
        "Avg latency | Tokens | Tool calls | Cost |"
    )
    print(
        "|---|---:|---:|---:|---:|---:|---:|---:|"
    )

    for mode, mode_records in grouped_by(records, "mode").items():
        tasks = len(mode_records)
        passed = sum(
            1
            for record in mode_records
            if record.get("passed")
        )
        print(
            f"| {mode} | {tasks} | {passed}/{tasks} | "
            f"{percentage(passed, tasks)} | "
            f"{average_latency(mode_records)} ms | "
            f"{total_tokens(mode_records):,} | "
            f"{total_tool_calls(mode_records)} | "
            f"{total_cost(mode_records):.4f} |"
        )


def print_task_table(records: list[dict]) -> None:
    print("## Tasks")
    print()
    print(
        "| Task | Mode | Passed | Status | Latency | "
        "Tokens | Tool calls | Cost | Missing |"
    )
    print(
        "|---|---|---:|---|---:|---:|---:|---:|---:|"
    )

    for record in records:
        usage = record.get("usage", {})
        evaluation = record.get("evaluation", {})
        missing_count = sum(
            len(evaluation.get(key, []) or [])
            for key in [
                "missing_mentions",
                "missing_files",
                "missing_symbols",
            ]
        )

        print(
            f"| {record.get('task_id')} | "
            f"{record.get('mode')} | "
            f"{yes_no(record.get('passed'))} | "
            f"{record.get('status')} | "
            f"{record.get('latency_ms', 0)} ms | "
            f"{usage.get('total_tokens', 0):,} | "
            f"{record.get('tool_calls', 0)} | "
            f"{float(usage.get('cost', 0)):.4f} | "
            f"{missing_count} |"
        )


def comparison_table_rows(records: list[dict]) -> list[dict]:
    by_task = grouped_by(records, "task_id")
    rows = []

    for task_id, task_records in by_task.items():
        by_mode = {
            record.get("mode"): record
            for record in task_records
        }

        if len(by_mode) < 2:
            continue

        baseline = by_mode.get("baseline")
        indexing = (
            by_mode.get("indexed_agent")
            or by_mode.get("evidence_packet")
            or by_mode.get("indexing")
        )

        if baseline is None or indexing is None:
            continue

        rows.append(
            {
                "task_id": task_id,
                "baseline": baseline,
                "indexing": indexing,
            }
        )

    return rows


def print_comparison_table(rows: list[dict]) -> None:
    print("## Baseline vs indexing")
    print()
    print(
        "| Task | Baseline | Indexing | Latency delta | "
        "Token delta | Cost delta |"
    )
    print("|---|---:|---:|---:|---:|---:|")

    for row in rows:
        baseline = row["baseline"]
        indexing = row["indexing"]

        latency_delta = (
            indexing.get("latency_ms", 0)
            - baseline.get("latency_ms", 0)
        )
        token_delta = (
            get_total_tokens(indexing)
            - get_total_tokens(baseline)
        )
        cost_delta = (
            get_cost(indexing)
            - get_cost(baseline)
        )

        print(
            f"| {row['task_id']} | "
            f"{yes_no(baseline.get('passed'))} | "
            f"{yes_no(indexing.get('passed'))} | "
            f"{latency_delta:+,} ms | "
            f"{token_delta:+,} | "
            f"{cost_delta:+.4f} |"
        )


def grouped_by(
    records: list[dict],
    key: str,
) -> dict[str, list[dict]]:
    grouped = defaultdict(list)

    for record in records:
        grouped[str(record.get(key))].append(record)

    return dict(grouped)


def average_latency(records: list[dict]) -> int:
    return round(
        sum(record.get("latency_ms", 0) for record in records)
        / len(records)
    )


def total_tokens(records: list[dict]) -> int:
    return sum(get_total_tokens(record) for record in records)


def total_tool_calls(records: list[dict]) -> int:
    return sum(record.get("tool_calls", 0) for record in records)


def total_cost(records: list[dict]) -> float:
    return sum(get_cost(record) for record in records)


def get_total_tokens(record: dict) -> int:
    return int(
        (record.get("usage") or {}).get(
            "total_tokens",
            0,
        )
    )


def get_cost(record: dict) -> float:
    return float(
        (record.get("usage") or {}).get(
            "cost",
            0,
        )
    )


def percentage(
    numerator: int,
    denominator: int,
) -> str:
    if denominator == 0:
        return "0.0%"

    return f"{(numerator / denominator) * 100:.1f}%"


def yes_no(value) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    main()
