#!/usr/bin/env python3
"""Build mixed real-dataset prompts for EOS signal validation."""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def load_dataset_rows(name: str, config: str | None, split: str) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except Exception as exc:
        raise RuntimeError(
            "The 'datasets' package is required. Install it with "
            "`python -m pip install datasets`."
        ) from exc

    dataset = load_dataset(name, config, split=split) if config else load_dataset(name, split=split)
    return [dict(row) for row in dataset]


def sample_rows(rows: list[dict[str, Any]], limit: int, rng: random.Random) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return rows
    indexes = rng.sample(range(len(rows)), limit)
    return [rows[i] for i in indexes]


def wmt_prompts(limit: int, rng: random.Random) -> Iterable[dict[str, str]]:
    rows = sample_rows(load_dataset_rows("wmt14", "de-en", "test"), limit, rng)
    for idx, row in enumerate(rows):
        translation = row["translation"]
        source = translation["de"]
        target = translation["en"]
        yield {
            "id": f"wmt14_de_en_{idx:04d}",
            "source": "wmt14_de_en",
            "prompt": f"Translate this German sentence to English:\n\n{source}",
            "reference": target,
        }


def triviaqa_prompts(limit: int, rng: random.Random) -> Iterable[dict[str, str]]:
    rows = sample_rows(load_dataset_rows("trivia_qa", "rc.nocontext", "validation"), limit, rng)
    for idx, row in enumerate(rows):
        answer = row.get("answer", {})
        aliases = answer.get("aliases") or []
        yield {
            "id": f"triviaqa_{idx:04d}",
            "source": "triviaqa",
            "prompt": f"Answer the question briefly:\n\n{row['question']}",
            "reference": aliases[0] if aliases else answer.get("value", ""),
        }


def gsm8k_prompts(limit: int, rng: random.Random) -> Iterable[dict[str, str]]:
    rows = sample_rows(load_dataset_rows("gsm8k", "main", "test"), limit, rng)
    for idx, row in enumerate(rows):
        yield {
            "id": f"gsm8k_{idx:04d}",
            "source": "gsm8k",
            "prompt": f"Solve this math problem step by step:\n\n{row['question']}",
            "reference": row.get("answer", ""),
        }


def humaneval_prompts(limit: int, rng: random.Random) -> Iterable[dict[str, str]]:
    rows = sample_rows(load_dataset_rows("openai/openai_humaneval", None, "test"), limit, rng)
    for idx, row in enumerate(rows):
        yield {
            "id": f"humaneval_{idx:04d}",
            "source": "humaneval",
            "prompt": (
                "Complete the Python function. Include the implementation only.\n\n"
                f"{row['prompt']}"
            ),
            "reference": row.get("canonical_solution", ""),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-per-source", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--sources",
        default="wmt,triviaqa,gsm8k,humaneval",
        help="Comma-separated subset of: wmt,triviaqa,gsm8k,humaneval",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    builders = {
        "wmt": wmt_prompts,
        "triviaqa": triviaqa_prompts,
        "gsm8k": gsm8k_prompts,
        "humaneval": humaneval_prompts,
    }

    selected = [source.strip() for source in args.sources.split(",") if source.strip()]
    unknown = sorted(set(selected) - set(builders))
    if unknown:
        raise ValueError(f"Unknown sources: {unknown}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.output.open("w", encoding="utf-8") as f:
        for source in selected:
            for row in builders[source](args.max_per_source, rng):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1

    print(f"Wrote {count} prompts to {args.output}")


if __name__ == "__main__":
    main()
