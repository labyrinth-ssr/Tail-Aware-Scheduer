# Serving Benchmark by Actual Output Length

Short requests are classified as `output_len <= 64`. Long requests are classified from the actual generated token count, not from prompt labels or requested output length.

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
