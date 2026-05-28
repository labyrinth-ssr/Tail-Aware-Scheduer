# Tail-Aware Scheduler Unit Tests

This document describes the unit tests added for the tail-aware scheduling feature in `test_scheduler.py`.

## Overview

The tail-aware scheduler identifies "long" (tail-latency) requests that have exceeded a token threshold and deprioritizes them so that shorter, higher-priority requests get scheduled first. These tests cover the demotion logic, reordering, cleanup, EOS-based demotion suppression, metrics/logging, waiting-queue prioritization, and preemption.

## Tests

### `test_tail_aware_token_demotion_threshold`
Verifies that a request is promoted into the `tail_aware_long_req_ids` set once its cumulative output token count crosses the `VLLM_TAIL_AWARE_SHORT_THRESHOLD`. Before the threshold, the request stays classified as "high-priority"; after crossing it, it is demoted to "long".

### `test_tail_aware_reorder_running_with_long_quota`
Tests that `_reorder_running_for_tail_aware()` rearranges the running batch so that high-priority (short) requests appear before long requests, while respecting the `VLLM_TAIL_AWARE_LONG_QUOTA` ratio. This ensures the scheduler fills most of the batch budget with short requests and pushes long requests toward the tail of the batch.

### `test_tail_aware_cleanup_on_free_blocks`
Confirms that when a request finishes (via `finish_requests`), its ID is removed from `tail_aware_long_req_ids`. This prevents stale entries from accumulating and affecting future scheduling decisions.

### `test_tail_aware_eos_prevents_demotion`
Checks that a request whose recent P(EOS) values exceed `VLLM_TAIL_AWARE_EOS_THRESH` is **not** demoted, even if it has crossed the short-token threshold. The intuition is that a high EOS probability signals the request is about to finish, so demoting it would be counterproductive.

### `test_tail_aware_eos_low_allows_demotion`
The complement of the previous test: when all recent P(EOS) values are below the threshold, demotion proceeds normally after the token count exceeds the short threshold.

### `test_tail_aware_eos_window_sliding`
Validates that only the last `VLLM_TAIL_AWARE_EOS_WINDOW` EOS probabilities are considered. An older high-EOS value that has slid out of the window no longer blocks demotion.

### `test_tail_aware_eos_prob_stored_on_request`
A basic sanity check that `recent_eos_probs` is initialized to an empty list on a new request and correctly accumulates appended probability values.

### `test_tail_aware_demotion_metrics_and_log`
Ensures that when a demotion occurs:
1. `tail_aware_demotion_count` increments.
2. `tail_aware_demotion_output_tokens` records the token count at demotion time.
3. `make_stats()` surfaces these counters.
4. A JSONL log entry with `"event": "demotion"` is written to the file specified by `VLLM_TAIL_AWARE_LOG_PATH`.

### `test_tail_aware_schedule_step_metrics_and_log`
Verifies per-step scheduling metrics recorded by `_record_tail_aware_schedule_metrics`:
1. `tail_aware_scheduled_high_reqs` and `tail_aware_scheduled_long_reqs` count how many high-priority vs. long requests were scheduled in the step.
2. `make_stats()` exposes these values.
3. A JSONL log entry with `"event": "schedule_step"` is written, including a `request_queue_classes` map that labels each request as `"high"` or `"long"`.

### `test_tail_aware_waiting_prefers_high_over_long`
Tests that `_select_waiting_queue_for_scheduling()` reorders the waiting queue so that high-priority requests are dequeued before long requests, even if the long request was added first.

### `test_tail_aware_preempts_long_for_high_waiter`
End-to-end test of preemption: when the batch is full with a long request and a new high-priority request arrives, the scheduler preempts the long request (moving it back to the waiting queue with `PREEMPTED` status) and schedules the high-priority request instead. Also verifies that the preempted request retains its long classification in `tail_aware_long_req_ids`.