# Tail-Aware Scheduler Implementation TODO

## Completed

### Phase 1: Token-Count Demotion

- Env-gated tail-aware scheduling (`VLLM_TAIL_AWARE_SCHEDULING=1`).
- Demote requests after `VLLM_TAIL_AWARE_SHORT_THRESHOLD` output tokens.
- Keep demoted request IDs in a long set.
- Reorder the running list to approximate `VLLM_TAIL_AWARE_LONG_QUOTA`.
- Clean up long-set state when requests are freed.
- Three unit tests: threshold, reorder, cleanup.

### Phase 2: P(EOS)-Aware Demotion

- Extract P(EOS) from raw logits in `Sampler.forward()` using
  `gather + logsumexp`, before logits processors are applied.
- Propagate P(EOS) through both sync and async GPU-to-CPU copy paths
  in `gpu_model_runner.py`.
- Build `eos_token_ids` tensor in `gpu_input_batch.py`, gated behind
  `VLLM_TAIL_AWARE_SCHEDULING`.
- Store per-step P(EOS) history on `Request.recent_eos_probs`.
- Check sliding window `max(recent_eos_probs[-eos_window:])` in
  `_maybe_demote_tail_aware_request()`: high P(EOS) prevents demotion.
- Four new unit tests: eos_prevents_demotion, eos_low_allows_demotion,
  eos_window_sliding, eos_prob_stored_on_request.
- All 7 tail-aware tests pass on the Kubernetes cluster.

### Offline EOS Signal Validation

- Smoke run with Qwen2.5-7B-Instruct on 10 prompts.
- Strong early P(EOS) separation: AUC = 1.0 for short/long classification.
- Stable parameter region: `N=8-32, short_threshold>=64, eos_thresh=0.001-0.1`.

### Scheduler Metrics and Serving Benchmark

- Added tail-aware scheduler metrics:

  - demotion count;
  - output token count at demotion;
  - queue class per request (`high` vs `long`);
  - per-step scheduled high/long request counts.

- Added optional JSONL schedule logging through `VLLM_TAIL_AWARE_LOG_PATH`.
- Added a Kubernetes serving benchmark job for Qwen2.5-7B-Instruct:

  - baseline FCFS;
  - token-count-only tail-aware;
  - EOS-aware tail-aware;
  - quota ablations at `0.1`, `0.2`, and `0.3`.

- Fixed the serving benchmark environment to use the same working install path
  as the scheduler pytest job:

  - `VLLM_USE_PRECOMPILED=1 uv pip install --system -e '.[bench]'`;
  - no `PYTHONPATH=/src/vllm`, so the precompiled `vllm._C` extension is used;
  - `--ready-check-timeout-sec 900` for server startup polling.

- Initial serving result on the mixed workload showed baseline was faster in
  aggregate metrics. The main causes were:

  - per-step JSONL logging overhead;
  - token-count-only run was initially misconfigured with `eos_thresh=0.0`,
    which prevented demotion;
  - the first version only reordered already-running requests and did not
    improve admission under full batch occupancy.

### Waiting Priority and Preemption

- Added tail-aware waiting priority:

  - when tail-aware scheduling is enabled, waiting high/probation requests are
    promoted ahead of demoted long requests;
  - this approximates the original two-queue design without replacing vLLM's
    request queue implementation.

- Added conservative tail-aware preemption:

  - if `running` is full, a high/probation request is waiting, and a demoted
    long request is running, preempt one demoted long request;
  - preemption uses vLLM's existing `_preempt_request()` path, so this is
    recompute preemption rather than KV swap-out.

- Added unit tests for:

  - waiting queue high-over-long priority;
  - preempting a running demoted long request to admit a high/probation waiter.

- The tail-aware scheduler unit tests pass on the Kubernetes cluster.

## Immediate TODO

1. Re-run serving benchmark with the updated implementation:

   - logging disabled by default;
   - token-count-only demotion fixed with `eos_thresh=1.0`;
   - waiting priority and recompute preemption enabled;
   - result analysis split by actual generated output length
     (`output_len <= short_threshold` vs `output_len > short_threshold`).

2. Larger offline validation with real datasets (WMT, TriviaQA, GSM8K,
   HumanEval) to confirm P(EOS) signal generalizes beyond smoke test.

## Known Design Gaps

- The current waiting-priority implementation approximates the full two-queue
  design inside vLLM's existing request queue. It is not a separate durable
  short/probation queue plus long queue.
- `long_quota` is currently approximate because vLLM schedules by token budget,
  while the patch reorders requests.
- Preemption is recompute-based through vLLM's existing preemption path. It is
  not KV swap-out, so preempting long requests can increase wasted work.
- Aggregate p95/p99 can still be dominated by real long requests. The primary
  target metric should be short-request TTFT/E2E tail latency under mixed
  workload, with long-request degradation reported separately.

## Experiment Matrix

Use a mixed workload with short translation/QA/summarization and long
reasoning/code prompts.

Primary metrics:

- short-request TTFT and end-to-end latency, especially p50/p90/p99;
- long-request throughput and starvation rate;
- aggregate tokens/sec;
- demotion precision and false demotion rate;
- GPU utilization if available from cluster telemetry.

Suggested runs:

```text
baseline:
  VLLM_TAIL_AWARE_SCHEDULING=0

token-count only:
  VLLM_TAIL_AWARE_SCHEDULING=1
  VLLM_TAIL_AWARE_SHORT_THRESHOLD=64
  VLLM_TAIL_AWARE_LONG_QUOTA=0.2

eos-aware:
  VLLM_TAIL_AWARE_SCHEDULING=1
  VLLM_TAIL_AWARE_SHORT_THRESHOLD=64
  VLLM_TAIL_AWARE_LONG_QUOTA=0.2
  VLLM_TAIL_AWARE_EOS_WINDOW=16
  VLLM_TAIL_AWARE_EOS_THRESH=0.05

quota sweep:
  VLLM_TAIL_AWARE_LONG_QUOTA in 0.1,0.2,0.3,0.5

eos parameter sweep:
  VLLM_TAIL_AWARE_EOS_WINDOW in 8,16,32
  VLLM_TAIL_AWARE_EOS_THRESH in 0.001,0.005,0.01,0.05
```

## Stretch Goals

- Implement real waiting-queue separation for new/probation vs demoted long
  requests.
- Add aging or a minimum long-service guarantee if starvation appears in
  benchmark traces.
- Add optional request-arrival length prediction as an ablation, not as the
  default design.
