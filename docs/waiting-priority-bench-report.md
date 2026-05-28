# Serving Benchmark by Actual Output Length

## Experiment Setup

- Cluster job: `tail-aware-serving-experiment` in namespace `ucsc-hsc`.
- Model: `Qwen/Qwen2.5-7B-Instruct`.
- Server: `vllm serve` with `--max-num-seqs 16` and
  `--max-num-batched-tokens 2048`.
- Benchmark: `vllm bench serve`, custom mixed prompt set, `200` requests,
  `8` RPS, `temperature=0`, `--disable-shuffle`.
- Runtime fix: `FLASHINFER_DISABLE_VERSION_CHECK=1` was set to bypass a
  `flashinfer` / `flashinfer-jit-cache` version mismatch in the cluster image.
- Tail-aware logging was disabled for this run, so old `*.tail_aware.jsonl`
  files remaining in the PVC should not be used for this experiment.

## Cases

- `baseline`: vLLM default FCFS scheduling.
- `token_count_only`: tail-aware scheduling enabled, token-count demotion only
  (`eos_thresh=1.0`, `long_quota=0.2`).
- `eos_aware`: EOS-aware demotion (`eos_thresh=0.05`, `long_quota=0.2`).
- `quota_0_1`: EOS-aware demotion with `long_quota=0.1`.
- `quota_0_3`: EOS-aware demotion with `long_quota=0.3`.

Short requests are classified as `output_len <= 64`. Long requests are classified from the actual generated token count, not from prompt labels or requested output length.

The classification is post-hoc: each completed request is labeled from its
actual generated token count in the benchmark result JSON. This is the right
metric split for this scheduler because the scheduler does not know the true
completion length at admission time.

## Class Summary

| case | class | count | failed | mean output | TTFT p95 ms | TTFT p99 ms | E2E p95 ms | E2E p99 ms | req/s | out tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | all | 200 | 0 | 107.92 | 5130.08 | 5413.16 | 10120.01 | 10476.06 | 5.76 | 621.90 |
| baseline | short | 124 | 0 | 17.16 | 5211.38 | 5401.79 | 5503.48 | 5834.60 |  |  |
| baseline | long | 76 | 0 | 256 | 5000.70 | 5219.19 | 10352.92 | 10612.11 |  |  |
| eos_aware | all | 200 | 0 | 107.91 | 280.00 | 343.18 | 30161.92 | 32773.94 | 5.78 | 623.84 |
| eos_aware | short | 124 | 0 | 17.15 | 280.01 | 348.61 | 1012.50 | 1048.64 |  |  |
| eos_aware | long | 76 | 0 | 256 | 261.86 | 322.97 | 31851.87 | 33630.41 |  |  |
| quota_0_1 | all | 200 | 0 | 107.88 | 1390.36 | 1619.93 | 29938.46 | 32855.34 | 5.75 | 620.67 |
| quota_0_1 | short | 124 | 0 | 17.10 | 1447.42 | 1701.76 | 1736.16 | 2210.86 |  |  |
| quota_0_1 | long | 76 | 0 | 256 | 863.55 | 1229.76 | 32018.06 | 33797.23 |  |  |
| quota_0_3 | all | 200 | 0 | 107.89 | 431.52 | 526.47 | 29987.50 | 32711.10 | 5.79 | 624.93 |
| quota_0_3 | short | 124 | 0 | 17.12 | 419.21 | 522.22 | 1040.83 | 1185.07 |  |  |
| quota_0_3 | long | 76 | 0 | 256 | 456.38 | 535.39 | 31784.04 | 33564.13 |  |  |
| token_count_only | all | 200 | 0 | 107.83 | 231.84 | 313.75 | 30023.55 | 32890.70 | 5.75 | 620.21 |
| token_count_only | short | 124 | 0 | 17.01 | 229.28 | 272.85 | 947.57 | 1037.91 |  |  |
| token_count_only | long | 76 | 0 | 256 | 261.91 | 321.08 | 31927.18 | 33629.35 |  |  |

## Delta vs Baseline

| case | class | TTFT p95 | TTFT p99 | E2E p95 | E2E p99 |
|---|---:|---:|---:|---:|---:|
| eos_aware | all | -94.5% | -93.7% | +198.0% | +212.8% |
| eos_aware | short | -94.6% | -93.5% | -81.6% | -82.0% |
| eos_aware | long | -94.8% | -93.8% | +207.7% | +216.9% |
| quota_0_1 | all | -72.9% | -70.1% | +195.8% | +213.6% |
| quota_0_1 | short | -72.2% | -68.5% | -68.5% | -62.1% |
| quota_0_1 | long | -82.7% | -76.4% | +209.3% | +218.5% |
| quota_0_3 | all | -91.6% | -90.3% | +196.3% | +212.2% |
| quota_0_3 | short | -92.0% | -90.3% | -81.1% | -79.7% |
| quota_0_3 | long | -90.9% | -89.7% | +207.0% | +216.3% |
| token_count_only | all | -95.5% | -94.2% | +196.7% | +214.0% |
| token_count_only | short | -95.6% | -94.9% | -82.8% | -82.2% |
| token_count_only | long | -94.8% | -93.8% | +208.4% | +216.9% |

## Analysis

Waiting priority plus recompute preemption achieves the intended short-request
latency effect. Compared with baseline, short-request p99 TTFT drops from
`5401.79 ms` to `272.85 ms` in `token_count_only`, `348.61 ms` in `eos_aware`,
and `522.22 ms` in `quota_0_3`. Short-request p99 end-to-end latency also drops
from `5834.60 ms` to roughly `1.0-1.2 s` for the strongest tail-aware cases.

Throughput is roughly unchanged. Baseline output throughput is `621.90 tok/s`;
the tail-aware cases are between `620.21 tok/s` and `624.93 tok/s`. This means
the short-request improvement is not coming from a large throughput loss.

The cost is severe long-request degradation. Baseline long p99 E2E is
`10612.11 ms`, while the tail-aware cases are around `33.6 s`. Aggregate p99
E2E also gets much worse because it is dominated by long requests: baseline is
`10476.06 ms`, while tail-aware cases are around `32.7-32.9 s`.

The current preemption policy is therefore too aggressive. It proves that the
mechanism can protect short requests, but it does so by repeatedly pushing
demoted long requests out of the running set. Since the current implementation
uses vLLM's recompute preemption path rather than KV swap-out, preempted long
requests pay extra recomputation cost.

## Takeaways

- The design goal should be evaluated on short-request TTFT/E2E tail latency,
  not only aggregate p95/p99.
- Waiting priority and preemption are effective for short requests under mixed
  load.
- The current recompute-preemption policy is not production-ready because it
  over-penalizes long requests.
- The next implementation should keep waiting priority, but make preemption
  bounded and optional.

## Next Steps

- Add a separate preemption gate such as `VLLM_TAIL_AWARE_PREEMPTION`.
- Add a per-request preemption cap, for example
  `VLLM_TAIL_AWARE_MAX_PREEMPTS_PER_REQ=1`.
- Only preempt a long request when the running long ratio is above
  `VLLM_TAIL_AWARE_LONG_QUOTA`.
- Add long aging or a starvation guard so demoted long requests can regain
  service after waiting too long.
- Re-run three cases: baseline, waiting-priority-only, and bounded preemption.
