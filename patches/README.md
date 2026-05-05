# vLLM Patches

## `vllm-tail-aware-token-demotion.patch`

Patch target:

```text
vLLM upstream commit: 48954de
file: vllm/v1/core/sched/scheduler.py
```

Current behavior:

- Default vLLM behavior is unchanged.
- Enable with `VLLM_TAIL_AWARE_SCHEDULING=1`.
- Requests are demoted after `VLLM_TAIL_AWARE_SHORT_THRESHOLD` generated tokens, default `64`.
- Demoted requests are reordered behind probation/short requests.
- `VLLM_TAIL_AWARE_LONG_QUOTA`, default `0.2`, interleaves roughly one long request after four high-priority requests.

This is the first integration skeleton. It is intentionally token-count-only. The `P(EOS)` signal still needs a model-runner/logprob hook because scheduler output only receives sample logprobs when the request asks for logprobs.
