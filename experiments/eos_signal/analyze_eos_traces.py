#!/usr/bin/env python3
"""Analyze P(EOS) traces and sweep demotion parameters."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

try:
    import numpy as np
except Exception:
    np = None


def parse_ints(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x.strip()]


def parse_floats(value: str) -> list[float]:
    return [float(x) for x in value.split(",") if x.strip()]


def read_traces(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def max_recent(values: list[float], end_exclusive: int, window: int) -> float:
    start = max(0, end_exclusive - window)
    recent = values[start:end_exclusive]
    return max(recent) if recent else 0.0


def first_demotion_step(
    p_eos: list[float],
    output_len: int,
    window: int,
    short_threshold: int,
    eos_thresh: float,
) -> int | None:
    last_observable_step = min(output_len, len(p_eos))
    for step in range(window, last_observable_step + 1):
        if step >= short_threshold and max_recent(p_eos, step, window) <= eos_thresh:
            return step
    return None


def safe_auc(labels: list[int], scores: list[float]) -> float | None:
    if len(set(labels)) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score

        return float(roc_auc_score(labels, scores))
    except Exception:
        positives = [s for y, s in zip(labels, scores) if y == 1]
        negatives = [s for y, s in zip(labels, scores) if y == 0]
        total = len(positives) * len(negatives)
        if total == 0:
            return None
        wins = 0.0
        for p in positives:
            for n in negatives:
                wins += 1.0 if p > n else 0.5 if p == n else 0.0
        return wins / total


def percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * (pct / 100.0)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return float(sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac)


def correlation(xs: list[int], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    if np is not None:
        return float(np.corrcoef(xs, ys)[0, 1])
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_den = sum((x - x_mean) ** 2 for x in xs) ** 0.5
    y_den = sum((y - y_mean) ** 2 for y in ys) ** 0.5
    if x_den == 0.0 or y_den == 0.0:
        return 0.0
    return numerator / (x_den * y_den)


def maybe_plot(rows: list[dict[str, Any]], out_dir: Path, length_threshold: int) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return

    plt.figure(figsize=(8, 5))
    for row in rows[:200]:
        p_eos = row["p_eos"]
        if not p_eos:
            continue
        color = "tab:blue" if row["output_len"] < length_threshold else "tab:orange"
        alpha = 0.18 if row["output_len"] < length_threshold else 0.12
        plt.plot(range(1, len(p_eos) + 1), p_eos, color=color, alpha=alpha)
    plt.yscale("log")
    plt.xlabel("Generated token step")
    plt.ylabel("P(EOS)")
    plt.title("P(EOS) trajectories: short blue, long orange")
    plt.tight_layout()
    plt.savefig(out_dir / "p_eos_trajectories.png", dpi=180)
    plt.close()

    lengths = [int(row["output_len"]) for row in rows]
    early_max = [max(row["p_eos"][: min(32, len(row["p_eos"]))] or [0.0]) for row in rows]
    plt.figure(figsize=(7, 5))
    plt.scatter(lengths, early_max, s=12, alpha=0.55)
    plt.yscale("log")
    plt.xlabel("Final output length")
    plt.ylabel("Max P(EOS) in first 32 generated tokens")
    plt.tight_layout()
    plt.savefig(out_dir / "early_p_eos_vs_length.png", dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--length-threshold", type=int, default=100)
    parser.add_argument("--n-values", default="8,16,32")
    parser.add_argument("--short-threshold-values", default="64,100,128")
    parser.add_argument("--eos-thresh-values", default="0.005,0.01,0.02,0.05,0.1")
    args = parser.parse_args()

    rows = read_traces(args.input)
    if not rows:
        raise ValueError(f"No traces found in {args.input}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    lengths = [int(row["output_len"]) for row in rows]
    labels_long = [1 if length >= args.length_threshold else 0 for length in lengths]
    early_scores = []
    inverse_early_scores = []
    for row in rows:
        p_eos = [float(x) for x in row.get("p_eos", [])]
        early = max(p_eos[: min(32, len(p_eos))] or [0.0])
        early_scores.append(early)
        inverse_early_scores.append(-early)

    corr = correlation(lengths, early_scores)
    auc_long_from_low_eos = safe_auc(labels_long, inverse_early_scores)
    short_count = sum(1 for x in lengths if x < args.length_threshold)
    long_count = len(rows) - short_count

    summary = {
        "num_traces": len(rows),
        "length_threshold": args.length_threshold,
        "short_count": short_count,
        "long_count": long_count,
        "output_len_median": statistics.median(lengths),
        "output_len_p90": percentile(lengths, 90),
        "corr_output_len_vs_max_p_eos_first_32": corr,
        "auc_long_from_low_max_p_eos_first_32": auc_long_from_low_eos,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    sweep_path = args.out_dir / "parameter_sweep.csv"
    n_values = parse_ints(args.n_values)
    short_threshold_values = parse_ints(args.short_threshold_values)
    eos_thresh_values = parse_floats(args.eos_thresh_values)

    with sweep_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "N",
            "short_threshold",
            "eos_thresh",
            "demoted",
            "demoted_true_long",
            "demotion_precision",
            "long_recall",
            "short_false_demote_rate",
            "median_demotion_step",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for n in n_values:
            for short_threshold in short_threshold_values:
                for eos_thresh in eos_thresh_values:
                    demotion_steps: list[int] = []
                    demoted_true_long = 0
                    short_false_demote = 0
                    for row, is_long in zip(rows, labels_long):
                        step = first_demotion_step(
                            [float(x) for x in row.get("p_eos", [])],
                            int(row["output_len"]),
                            n,
                            short_threshold,
                            eos_thresh,
                        )
                        if step is None:
                            continue
                        demotion_steps.append(step)
                        if is_long:
                            demoted_true_long += 1
                        else:
                            short_false_demote += 1
                    demoted = len(demotion_steps)
                    writer.writerow(
                        {
                            "N": n,
                            "short_threshold": short_threshold,
                            "eos_thresh": eos_thresh,
                            "demoted": demoted,
                            "demoted_true_long": demoted_true_long,
                            "demotion_precision": demoted_true_long / demoted if demoted else "",
                            "long_recall": demoted_true_long / long_count if long_count else "",
                            "short_false_demote_rate": short_false_demote / short_count if short_count else "",
                            "median_demotion_step": statistics.median(demotion_steps) if demotion_steps else "",
                        }
                    )

    maybe_plot(rows, args.out_dir, args.length_threshold)
    print(json.dumps(summary, indent=2))
    print(f"Wrote {sweep_path}")


if __name__ == "__main__":
    main()
