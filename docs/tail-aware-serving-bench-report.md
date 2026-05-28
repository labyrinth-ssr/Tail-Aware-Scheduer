# Tail-Aware Serving Benchmark Summary

Run copied from Kubernetes PVC path `/workspace/tail-aware-results/serving/qwen-mixed/`. Local copy: `results/cluster/serving/qwen-mixed/`.

## Setup

- Model: `Qwen/Qwen2.5-7B-Instruct`
- Benchmark: `vllm bench serve`, custom mixed JSONL workload, 200 requests, request rate 8 RPS
- Server: `vllm serve`, `--max-num-seqs 16`, `--max-num-batched-tokens 2048`
- Compared cases: baseline, token-count-only, EOS-aware, quota 0.1, quota 0.3

## Aggregate Results

| case | success | req/s | out tok/s | median TTFT | p99 TTFT | median E2E | p99 E2E |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 200/200 | 3.83 | 495.2 | 9531 ms | 20401 ms | 12211 ms | 26944 ms |
| token_count_only | 200/200 | 3.48 | 449.1 | 11348 ms | 24936 ms | 14558 ms | 32093 ms |
| eos_aware | 200/200 | 3.48 | 449.0 | 11294 ms | 24868 ms | 14522 ms | 32166 ms |
| quota_0_1 | 200/200 | 3.45 | 445.0 | 11403 ms | 25430 ms | 14545 ms | 32621 ms |
| quota_0_3 | 200/200 | 3.45 | 445.3 | 11443 ms | 25339 ms | 14840 ms | 32560 ms |

## Short vs Long Split

Short is defined as observed `output_len <= 64`; long is `output_len > 64`.

| case | group | n | median TTFT | p99 TTFT | median E2E | p99 E2E |
|---|---|---:|---:|---:|---:|---:|
| baseline | short | 107 | 9400 ms | 20391 ms | 9701 ms | 20856 ms |
| baseline | long | 93 | 9748 ms | 20345 ms | 16912 ms | 27023 ms |
| token_count_only | short | 107 | 11197 ms | 24838 ms | 11423 ms | 25364 ms |
| token_count_only | long | 93 | 11581 ms | 24959 ms | 19563 ms | 32307 ms |
| eos_aware | short | 107 | 11158 ms | 24867 ms | 11387 ms | 25291 ms |
| eos_aware | long | 93 | 11497 ms | 24885 ms | 19599 ms | 32250 ms |
| quota_0_1 | short | 107 | 11253 ms | 25394 ms | 11476 ms | 25917 ms |
| quota_0_1 | long | 93 | 11638 ms | 25458 ms | 19849 ms | 32788 ms |
| quota_0_3 | short | 107 | 11144 ms | 25337 ms | 11669 ms | 25823 ms |
| quota_0_3 | long | 93 | 11832 ms | 25334 ms | 19911 ms | 32700 ms |

## Tail-Aware Logs

| log | demotions | scheduled high reqs | scheduled long reqs |
|---|---:|---:|---:|
| eos_aware.tail_aware.jsonl | 94 | 8237 | 17954 |
| quota_0_1.tail_aware.jsonl | 94 | 8237 | 17954 |
| quota_0_3.tail_aware.jsonl | 94 | 8237 | 17954 |
| token_count_only.tail_aware.jsonl | 0 | 26191 | 0 |

## Findings

1. Baseline won this run. Tail-aware cases had lower throughput and higher TTFT/E2E latency than baseline.
2. The likely reasons are implementation-level: current tail-aware scheduling only reorders `running` requests, does not prioritize the `waiting` queue, and does not preempt or evict long-running requests. Under high occupancy, new short requests can still wait behind resident long requests.
3. EOS-aware scheduling adds real overhead: P(EOS) computation, GPU-to-CPU propagation, per-request history updates, and JSONL logging. The run with logging showed roughly 10% lower output throughput than baseline.
4. The token-count-only ablation in this run was misconfigured. It used `VLLM_TAIL_AWARE_EOS_THRESH=0.0`; because the code prevents demotion when recent P(EOS) is greater than the threshold, this caused zero demotions. It should be rerun with `VLLM_TAIL_AWARE_EOS_THRESH=1.0` or with a dedicated EOS-gate disable flag.

## Next Run

- Disable per-step tail-aware JSONL logging by unsetting `VLLM_TAIL_AWARE_LOG_PATH`.
- Rerun token-count-only with `VLLM_TAIL_AWARE_EOS_THRESH=1.0`.
- Keep the same workload and server settings for comparability.
