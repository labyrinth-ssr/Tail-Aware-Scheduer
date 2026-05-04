#!/usr/bin/env python3
"""Collect per-step EOS probabilities for offline scheduler analysis."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "prompt" not in row:
                raise ValueError(f"{path}:{line_no} is missing required field 'prompt'")
            rows.append(row)
    return rows


def eos_token_ids(tokenizer: Any) -> list[int]:
    ids: set[int] = set()
    if tokenizer.eos_token_id is not None:
        if isinstance(tokenizer.eos_token_id, list):
            ids.update(int(x) for x in tokenizer.eos_token_id)
        else:
            ids.add(int(tokenizer.eos_token_id))
    for token in ("<|im_end|>", "<|endoftext|>"):
        token_id = tokenizer.convert_tokens_to_ids(token)
        if token_id is not None and token_id != tokenizer.unk_token_id:
            ids.add(int(token_id))
    if not ids:
        raise ValueError("Tokenizer does not expose an EOS token id")
    return sorted(ids)


def format_prompt(tokenizer: Any, prompt: str) -> str:
    if getattr(tokenizer, "chat_template", None):
        messages = [{"role": "user", "content": prompt}]
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    return prompt


def input_device(model: Any) -> torch.device:
    return next(model.parameters()).device


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Hugging Face model id or local path")
    parser.add_argument("--input", required=True, type=Path, help="JSONL prompts")
    parser.add_argument("--output", required=True, type=Path, help="Output JSONL traces")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--dtype", default="auto", choices=("auto", "float16", "bfloat16", "float32"))
    parser.add_argument("--device-map", default="auto")
    args = parser.parse_args()

    prompts = read_jsonl(args.input)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    eos_ids = eos_token_ids(tokenizer)

    dtype_map = {
        "auto": "auto",
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=dtype_map[args.dtype],
        device_map=args.device_map,
        trust_remote_code=True,
    )
    model.eval()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    do_sample = args.temperature > 0.0

    with args.output.open("w", encoding="utf-8") as out:
        for row in tqdm(prompts, desc="collecting"):
            prompt = str(row["prompt"])
            formatted = format_prompt(tokenizer, prompt)
            inputs = tokenizer(formatted, return_tensors="pt")
            inputs = {k: v.to(input_device(model)) for k, v in inputs.items()}
            prompt_len = int(inputs["input_ids"].shape[1])

            generation_kwargs = {
                "max_new_tokens": args.max_new_tokens,
                "do_sample": do_sample,
                "return_dict_in_generate": True,
                "output_scores": True,
                "pad_token_id": tokenizer.eos_token_id,
            }
            if do_sample:
                generation_kwargs["temperature"] = args.temperature
                generation_kwargs["top_p"] = args.top_p

            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    **generation_kwargs,
                )

            sequence = generated.sequences[0]
            new_token_ids = sequence[prompt_len:].detach().cpu().tolist()
            p_eos: list[float] = []
            top_token_ids: list[int] = []

            for score in generated.scores:
                probs = torch.softmax(score[0].float(), dim=-1)
                eos_prob = float(probs[eos_ids].sum().detach().cpu())
                p_eos.append(eos_prob if math.isfinite(eos_prob) else 0.0)
                top_token_ids.append(int(torch.argmax(probs).detach().cpu()))

            emitted_eos = any(token_id in eos_ids for token_id in new_token_ids)
            text = tokenizer.decode(new_token_ids, skip_special_tokens=True)
            output_row = {
                "id": row.get("id"),
                "source": row.get("source"),
                "prompt": prompt,
                "model": args.model,
                "eos_token_ids": eos_ids,
                "max_new_tokens": args.max_new_tokens,
                "output_token_ids": new_token_ids,
                "output_len": len(new_token_ids),
                "emitted_eos": emitted_eos,
                "p_eos": p_eos,
                "top_token_ids": top_token_ids,
                "output_text": text,
            }
            out.write(json.dumps(output_row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
