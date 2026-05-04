# Tail-Aware Scheduler

Course project workspace for tail-aware LLM request scheduling. The implementation plan is intentionally staged:

1. Validate whether early `P(EOS)` traces predict final output length.
2. Sweep scheduler parameters on offline traces.
3. Integrate the selected policy into vLLM's scheduler.
4. Run serving benchmarks against FCFS and ablations.

## Current Recommendation

Do not start by editing vLLM directly. First collect offline traces with logit scores enabled and verify that `P(EOS)` separates short and long generations. This reduces the risk of spending time on scheduler integration before the core signal is validated.

One design correction matters before implementation: if `N=8-16` and `short_threshold=64`, a rule applied only once at step `N` will never demote anything because `tokens < short_threshold` is always true. The safer operational rule is:

```text
Before N generated tokens:
  keep request in probation.

At each decode step after N:
  if generated_tokens >= short_threshold
     and max(P_EOS over recent N tokens) <= eos_thresh:
       demote to long queue.
  else:
       keep request in probation.
```

This keeps the spirit of the proposal while making demotion reachable.

## Offline P(EOS) Analysis

Prepare a JSONL prompt file:

```jsonl
{"id":"wmt_0001","prompt":"Translate to French: The meeting starts at noon.","source":"wmt"}
{"id":"gsm8k_0001","prompt":"Solve step by step: ...","source":"gsm8k"}
```

Collect traces:

```bash
python3 experiments/eos_signal/collect_eos_traces.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --input data/prompts.jsonl \
  --output results/eos_signal/traces.jsonl \
  --max-new-tokens 512 \
  --temperature 0.0
```

Analyze signal quality and parameter sensitivity:

```bash
python3 experiments/eos_signal/analyze_eos_traces.py \
  --input results/eos_signal/traces.jsonl \
  --out-dir results/eos_signal \
  --length-threshold 100 \
  --n-values 8,16,32 \
  --short-threshold-values 64,100,128 \
  --eos-thresh-values 0.005,0.01,0.02,0.05,0.1
```

Outputs include summary metrics, optional plots, and a CSV sweep table.

## vLLM Integration Plan

After the offline signal looks useful, clone or fork vLLM and keep the scheduler changes small:

- Add per-request queue state: `probation`, `confirmed_short`, `long`.
- Track generated token count and recent `P(EOS)` in request metadata.
- Replace the waiting/running selection policy with two queues plus `long_quota`.
- Preserve existing continuous batching, KV cache handling, and model execution.

Target file from the proposal: `vllm/v1/core/sched/scheduler.py`.
