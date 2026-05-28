# Tail-Aware Serving Benchmark Summary

Run copied from Kubernetes PVC path `/workspace/tail-aware-results/serving/qwen-mixed/`. Local copy: `results/cluster/serving/qwen-mixed/`.

## Setup

- Model: `Qwen/Qwen2.5-7B-Instruct`
- Benchmark: `vllm bench serve`, custom mixed JSONL workload, 200 requests, request rate 8 RPS
- Server: `vllm serve`, `--max-num-seqs 16`, `--max-num-batched-tokens 2048`
- Compared cases: baseline, token-count-only, EOS-aware, quota 0.1, quota 0.3

## Aggregate Results

| case             | success | req/s | out tok/s | median TTFT | p99 TTFT | median E2E |  p99 E2E |
| ---------------- | ------: | ----: | --------: | ----------: | -------: | ---------: | -------: |
| baseline         | 200/200 |  3.83 |     495.2 |     9531 ms | 20401 ms |   12211 ms | 26944 ms |
| token_count_only | 200/200 |  3.48 |     449.1 |    11348 ms | 24936 ms |   14558 ms | 32093 ms |
| eos_aware        | 200/200 |  3.48 |     449.0 |    11294 ms | 24868 ms |   14522 ms | 32166 ms |
| quota_0_1        | 200/200 |  3.45 |     445.0 |    11403 ms | 25430 ms |   14545 ms | 32621 ms |
| quota_0_3        | 200/200 |  3.45 |     445.3 |    11443 ms | 25339 ms |   14840 ms | 32560 ms |

## Short vs Long Split

Short is defined as observed `output_len <= 64`; long is `output_len > 64`.

| case             | group |    n | median TTFT | p99 TTFT | median E2E |  p99 E2E |
| ---------------- | ----- | ---: | ----------: | -------: | ---------: | -------: |
| baseline         | short |  107 |     9400 ms | 20391 ms |    9701 ms | 20856 ms |
| baseline         | long  |   93 |     9748 ms | 20345 ms |   16912 ms | 27023 ms |
| token_count_only | short |  107 |    11197 ms | 24838 ms |   11423 ms | 25364 ms |
| token_count_only | long  |   93 |    11581 ms | 24959 ms |   19563 ms | 32307 ms |
| eos_aware        | short |  107 |    11158 ms | 24867 ms |   11387 ms | 25291 ms |
| eos_aware        | long  |   93 |    11497 ms | 24885 ms |   19599 ms | 32250 ms |
| quota_0_1        | short |  107 |    11253 ms | 25394 ms |   11476 ms | 25917 ms |
| quota_0_1        | long  |   93 |    11638 ms | 25458 ms |   19849 ms | 32788 ms |
| quota_0_3        | short |  107 |    11144 ms | 25337 ms |   11669 ms | 25823 ms |
| quota_0_3        | long  |   93 |    11832 ms | 25334 ms |   19911 ms | 32700 ms |

## Tail-Aware Logs

| log                               | demotions | scheduled high reqs | scheduled long reqs |
| --------------------------------- | --------: | ------------------: | ------------------: |
| eos_aware.tail_aware.jsonl        |        94 |                8237 |               17954 |
| quota_0_1.tail_aware.jsonl        |        94 |                8237 |               17954 |
| quota_0_3.tail_aware.jsonl        |        94 |                8237 |               17954 |
| token_count_only.tail_aware.jsonl |         0 |               26191 |                   0 |

## Findings

1. Baseline won this run. Tail-aware cases had lower throughput and higher TTFT/E2E latency than baseline.
2. The likely reasons are implementation-level: current tail-aware scheduling only reorders `running` requests, does not prioritize the `waiting` queue, and does not preempt or evict long-running requests. Under high occupancy, new short requests can still wait behind resident long requests.
3. EOS-aware scheduling adds real overhead: P(EOS) computation, GPU-to-CPU propagation, per-request history updates, and JSONL logging. The run with logging showed roughly 10% lower output throughput than baseline.
4. The token-count-only ablation in this run was misconfigured. It used `VLLM_TAIL_AWARE_EOS_THRESH=0.0`; because the code prevents demotion when recent P(EOS) is greater than the threshold, this caused zero demotions. It should be rerun with `VLLM_TAIL_AWARE_EOS_THRESH=1.0` or with a dedicated EOS-gate disable flag.

## Next Run

- Disable per-step tail-aware JSONL logging by unsetting `VLLM_TAIL_AWARE_LOG_PATH`.
- Rerun token-count-only with `VLLM_TAIL_AWARE_EOS_THRESH=1.0`.
- Keep the same workload and server settings for comparability.

# Serving Benchmark by Actual Output Length

Short requests are classified as `output_len <= 64`. Long requests are classified from the actual generated token count, not from prompt labels or requested output length.

## Class Summary

| case             | class | count | failed | mean output | TTFT p95 ms | TTFT p99 ms | E2E p95 ms | E2E p99 ms | req/s | out tok/s |
| ---------------- | ----: | ----: | -----: | ----------: | ----------: | ----------: | ---------: | ---------: | ----: | --------: |
| baseline         |   all |   200 |      0 |      129.14 |    19947.24 |    20400.89 |   24742.04 |   26943.60 |  3.83 |    495.22 |
| baseline         | short |   107 |      0 |       18.88 |    19957.67 |    20390.56 |   20308.27 |   20856.32 |       |           |
| baseline         |  long |    93 |      0 |         256 |    18753.34 |    20345.08 |   25748.82 |   27022.70 |       |           |
| eos_aware        |   all |   200 |      0 |      129.14 |    24430.29 |    24867.73 |   29398.62 |   32166.42 |  3.48 |    448.98 |
| eos_aware        | short |   107 |      0 |       18.88 |    24437.31 |    24866.79 |   24807.01 |   25290.88 |       |           |
| eos_aware        |  long |    93 |      0 |         256 |    23168.34 |    24884.84 |   30882.64 |   32249.56 |       |           |
| quota_0_1        |   all |   200 |      0 |      129.14 |    24929.94 |    25430.15 |   29939.02 |   32620.72 |  3.45 |    445.03 |
| quota_0_1        | short |   107 |      0 |       18.88 |    24941.24 |    25394.43 |   25285.88 |   25916.92 |       |           |
| quota_0_1        |  long |    93 |      0 |         256 |    23716.46 |    25457.81 |   31407.11 |   32787.52 |       |           |
| quota_0_3        |   all |   200 |      0 |      129.14 |    24834.99 |    25338.97 |   29845.25 |   32559.81 |  3.45 |    445.31 |
| quota_0_3        | short |   107 |      0 |       18.88 |    24871.22 |    25336.94 |   25234.45 |   25822.99 |       |           |
| quota_0_3        |  long |    93 |      0 |         256 |    23627.75 |    25333.76 |   31344.15 |   32699.56 |       |           |
| token_count_only |   all |   200 |      0 |      129.14 |    24374.85 |    24935.69 |   29386.85 |   32092.86 |  3.48 |    449.08 |
| token_count_only | short |   107 |      0 |       18.88 |    24387.36 |    24838.19 |   24730.30 |   25364.09 |       |           |
| token_count_only |  long |    93 |      0 |         256 |    23255.63 |    24959.15 |   30944.38 |   32307.44 |       |           |

## Delta vs Baseline

| case             | class | TTFT p95 | TTFT p99 | E2E p95 | E2E p99 |
| ---------------- | ----: | -------: | -------: | ------: | ------: |
| eos_aware        |   all |   +22.5% |   +21.9% |  +18.8% |  +19.4% |
| eos_aware        | short |   +22.4% |   +22.0% |  +22.2% |  +21.3% |
| eos_aware        |  long |   +23.5% |   +22.3% |  +19.9% |  +19.3% |
| quota_0_1        |   all |   +25.0% |   +24.7% |  +21.0% |  +21.1% |
| quota_0_1        | short |   +25.0% |   +24.5% |  +24.5% |  +24.3% |
| quota_0_1        |  long |   +26.5% |   +25.1% |  +22.0% |  +21.3% |
| quota_0_3        |   all |   +24.5% |   +24.2% |  +20.6% |  +20.8% |
| quota_0_3        | short |   +24.6% |   +24.3% |  +24.3% |  +23.8% |
| quota_0_3        |  long |   +26.0% |   +24.5% |  +21.7% |  +21.0% |
| token_count_only |   all |   +22.2% |   +22.2% |  +18.8% |  +19.1% |
| token_count_only | short |   +22.2% |   +21.8% |  +21.8% |  +21.6% |
| token_count_only |  long |   +24.0% |   +22.7% |  +20.2% |  +19.6% |
