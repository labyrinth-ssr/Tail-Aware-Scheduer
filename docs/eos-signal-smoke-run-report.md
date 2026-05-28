# EOS Signal Smoke Run Summary

## Setup

- Environment: Nautilus Kubernetes cluster, namespace `ucsc-hsc`.
- Job: `tail-aware-eos-qwen-smoke`.
- Model: `Qwen/Qwen2.5-7B-Instruct`.
- Workload: 10 hand-written prompts, 6 short-style and 4 long-style.
- Max generation length: 256 new tokens.
- Result path copied locally: `results/cluster/qwen-smoke/`.

## Key Results

The smoke run produced 10 traces:

- 6 requests completed naturally and were labeled short under the 100-token threshold.
- 4 requests hit the 256-token cap without EOS and were labeled long.
- Median output length: 32 tokens.
- P90 output length: 256 tokens.

Early `P(EOS)` was strongly separated between short and long requests:

```text
corr(output_len, max P(EOS) in first 32 tokens) = -0.844
AUC for detecting long requests from low early P(EOS) = 1.0
```

## Parameter Sweep Takeaway

The most stable region in this smoke run was:

```text
N = 8, 16, or 32
short_threshold >= 64
eos_thresh = 0.001 to 0.1
```

In this region:

```text
demotion_precision = 1.0
long_recall = 1.0
short_false_demote_rate = 0.0
```

Using `short_threshold = 32` was too aggressive: it falsely demoted one 36-token short answer.

## Design Implication

This supports the revised demotion rule:

```text
After at least N generated tokens,
demote only if generated_tokens >= short_threshold
and recent max(P_EOS) <= eos_thresh.
```

A reasonable starting point for the scheduler is:

```text
N = 16 or 32
short_threshold = 64
eos_thresh = 0.01 or 0.05
```

## Limitations

This is only a sanity check. The sample size is small, prompts are hand-written, and all long requests were truncated at 256 tokens rather than naturally completed. The result is encouraging for using `P(EOS)`, but the next step should be a larger run with real datasets such as WMT, TriviaQA, GSM8K, and HumanEval.
