# Serving Benchmark by Actual Output Length

Short requests are classified as `output_len <= 64`. Long requests are classified from the actual generated token count, not from prompt labels or requested output length.

## Class Summary

| case | class | count | failed | mean output | TTFT p95 ms | TTFT p99 ms | E2E p95 ms | E2E p99 ms | req/s | out tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | all | 200 | 0 | 129.14 | 19947.24 | 20400.89 | 24742.04 | 26943.60 | 3.83 | 495.22 |
| baseline | short | 107 | 0 | 18.88 | 19957.67 | 20390.56 | 20308.27 | 20856.32 |  |  |
| baseline | long | 93 | 0 | 256 | 18753.34 | 20345.08 | 25748.82 | 27022.70 |  |  |
| eos_aware | all | 200 | 0 | 129.14 | 24430.29 | 24867.73 | 29398.62 | 32166.42 | 3.48 | 448.98 |
| eos_aware | short | 107 | 0 | 18.88 | 24437.31 | 24866.79 | 24807.01 | 25290.88 |  |  |
| eos_aware | long | 93 | 0 | 256 | 23168.34 | 24884.84 | 30882.64 | 32249.56 |  |  |
| quota_0_1 | all | 200 | 0 | 129.14 | 24929.94 | 25430.15 | 29939.02 | 32620.72 | 3.45 | 445.03 |
| quota_0_1 | short | 107 | 0 | 18.88 | 24941.24 | 25394.43 | 25285.88 | 25916.92 |  |  |
| quota_0_1 | long | 93 | 0 | 256 | 23716.46 | 25457.81 | 31407.11 | 32787.52 |  |  |
| quota_0_3 | all | 200 | 0 | 129.14 | 24834.99 | 25338.97 | 29845.25 | 32559.81 | 3.45 | 445.31 |
| quota_0_3 | short | 107 | 0 | 18.88 | 24871.22 | 25336.94 | 25234.45 | 25822.99 |  |  |
| quota_0_3 | long | 93 | 0 | 256 | 23627.75 | 25333.76 | 31344.15 | 32699.56 |  |  |
| token_count_only | all | 200 | 0 | 129.14 | 24374.85 | 24935.69 | 29386.85 | 32092.86 | 3.48 | 449.08 |
| token_count_only | short | 107 | 0 | 18.88 | 24387.36 | 24838.19 | 24730.30 | 25364.09 |  |  |
| token_count_only | long | 93 | 0 | 256 | 23255.63 | 24959.15 | 30944.38 | 32307.44 |  |  |

## Delta vs Baseline

| case | class | TTFT p95 | TTFT p99 | E2E p95 | E2E p99 |
|---|---:|---:|---:|---:|---:|
| eos_aware | all | +22.5% | +21.9% | +18.8% | +19.4% |
| eos_aware | short | +22.4% | +22.0% | +22.2% | +21.3% |
| eos_aware | long | +23.5% | +22.3% | +19.9% | +19.3% |
| quota_0_1 | all | +25.0% | +24.7% | +21.0% | +21.1% |
| quota_0_1 | short | +25.0% | +24.5% | +24.5% | +24.3% |
| quota_0_1 | long | +26.5% | +25.1% | +22.0% | +21.3% |
| quota_0_3 | all | +24.5% | +24.2% | +20.6% | +20.8% |
| quota_0_3 | short | +24.6% | +24.3% | +24.3% | +23.8% |
| quota_0_3 | long | +26.0% | +24.5% | +21.7% | +21.0% |
| token_count_only | all | +22.2% | +22.2% | +18.8% | +19.1% |
| token_count_only | short | +22.2% | +21.8% | +21.8% | +21.6% |
| token_count_only | long | +24.0% | +22.7% | +20.2% | +19.6% |
