#!/usr/bin/env python3
"""Analyze vLLM serving benchmark results by actual generated length."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


PERCENTILES = (50, 90, 95, 99)


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct / 100
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def load_result(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def request_rows(result: dict[str, Any], short_threshold: int) -> list[dict[str, Any]]:
    output_lens = result.get("output_lens", [])
    ttfts = result.get("ttfts", [])
    itls = result.get("itls", [])
    input_lens = result.get("input_lens", [])
    errors = result.get("errors", [])

    row_count = min(len(output_lens), len(ttfts), len(itls))
    rows = []
    for idx in range(row_count):
        output_len = int(output_lens[idx] or 0)
        ttft_s = float(ttfts[idx] or 0.0)
        token_itls = itls[idx] or []
        e2e_s = ttft_s + sum(float(value) for value in token_itls)
        rows.append(
            {
                "index": idx,
                "class": "short" if output_len <= short_threshold else "long",
                "input_len": int(input_lens[idx]) if idx < len(input_lens) else 0,
                "output_len": output_len,
                "ttft_ms": ttft_s * 1000,
                "e2e_ms": e2e_s * 1000,
                "failed": bool(errors[idx]) if idx < len(errors) else False,
            }
        )
    return rows


def summarize_rows(case: str, result: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for cls in ("all", "short", "long"):
        selected = rows if cls == "all" else [row for row in rows if row["class"] == cls]
        ttfts = [row["ttft_ms"] for row in selected if not row["failed"]]
        e2es = [row["e2e_ms"] for row in selected if not row["failed"]]
        output_lens = [row["output_len"] for row in selected if not row["failed"]]
        summary: dict[str, Any] = {
            "case": case,
            "class": cls,
            "count": len(selected),
            "failed": sum(1 for row in selected if row["failed"]),
            "mean_output_len": mean(output_lens) if output_lens else 0.0,
            "request_throughput": result.get("request_throughput", 0.0) if cls == "all" else "",
            "output_throughput": result.get("output_throughput", 0.0) if cls == "all" else "",
        }
        for pct in PERCENTILES:
            summary[f"ttft_p{pct}_ms"] = percentile(ttfts, pct)
            summary[f"e2e_p{pct}_ms"] = percentile(e2es, pct)
        summaries.append(summary)
    return summaries


def format_float(value: Any) -> str:
    if value == "":
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def write_csv(path: Path, summaries: list[dict[str, Any]]) -> None:
    if not summaries:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)


def delta(value: Any, baseline: Any) -> str:
    if value == "" or baseline in ("", 0, 0.0):
        return ""
    return f"{((float(value) - float(baseline)) / float(baseline)) * 100:+.1f}%"


def write_markdown(path: Path, summaries: list[dict[str, Any]], threshold: int) -> None:
    baseline_by_class = {
        row["class"]: row
        for row in summaries
        if row["case"] == "baseline"
    }
    lines = [
        "# Serving Benchmark by Actual Output Length",
        "",
        f"Short requests are classified as `output_len <= {threshold}`. "
        "Long requests are classified from the actual generated token count, "
        "not from prompt labels or requested output length.",
        "",
        "## Class Summary",
        "",
        "| case | class | count | failed | mean output | TTFT p95 ms | TTFT p99 ms | E2E p95 ms | E2E p99 ms | req/s | out tok/s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case"]),
                    str(row["class"]),
                    str(row["count"]),
                    str(row["failed"]),
                    format_float(row["mean_output_len"]),
                    format_float(row["ttft_p95_ms"]),
                    format_float(row["ttft_p99_ms"]),
                    format_float(row["e2e_p95_ms"]),
                    format_float(row["e2e_p99_ms"]),
                    format_float(row["request_throughput"]),
                    format_float(row["output_throughput"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Delta vs Baseline",
            "",
            "| case | class | TTFT p95 | TTFT p99 | E2E p95 | E2E p99 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summaries:
        if row["case"] == "baseline":
            continue
        baseline = baseline_by_class.get(row["class"])
        if not baseline:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case"]),
                    str(row["class"]),
                    delta(row["ttft_p95_ms"], baseline["ttft_p95_ms"]),
                    delta(row["ttft_p99_ms"], baseline["ttft_p99_ms"]),
                    delta(row["e2e_p95_ms"], baseline["e2e_p95_ms"]),
                    delta(row["e2e_p99_ms"], baseline["e2e_p99_ms"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    parser.add_argument("--short-threshold", type=int, default=64)
    parser.add_argument("--out-prefix", default="by_output_len")
    args = parser.parse_args()

    result_paths = sorted(args.result_dir.glob("*.json"))
    if not result_paths:
        raise SystemExit(f"No JSON result files found in {args.result_dir}")

    summaries: list[dict[str, Any]] = []
    for result_path in result_paths:
        result = load_result(result_path)
        case = str(result.get("case") or result_path.stem)
        rows = request_rows(result, args.short_threshold)
        summaries.extend(summarize_rows(case, result, rows))

    csv_path = args.result_dir / f"{args.out_prefix}.csv"
    md_path = args.result_dir / f"{args.out_prefix}.md"
    write_csv(csv_path, summaries)
    write_markdown(md_path, summaries, args.short_threshold)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
