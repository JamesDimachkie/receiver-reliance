# Native-records usefulness proof -- results

| arm | n | detected | missed | false holds | detection rate | false-hold rate |
|---|---|---|---|---|---|---|
| baseline | 408 | 17 | 1 | 0 | 0.9444 | 0.0 |
| b1 | 408 | 18 | 0 | 133 | 1.0 | 0.341 |
| b1_calibrated | 408 | 18 | 0 | 0 | 1.0 | 0.0 |

## Per defect type (caught / n)

| defect type | baseline | b1 | b1_calibrated |
|---|---|---|---|
| lifecycle_order_violation | 3/3 | 3/3 | 3/3 |
| missing_reference_target | 3/3 | 3/3 | 3/3 |
| pin_hash_mismatch | 3/3 | 3/3 | 3/3 |
| recorded_use_outside_declared_scope | 3/3 | 3/3 | 3/3 |
| reliance_on_superseded_version | 0/1 | 1/1 | 1/1 |
| stale_reference_path | 5/5 | 5/5 | 5/5 |

## Per family false holds (fp/clean-n)

| family | baseline | b1 | b1_calibrated |
|---|---|---|---|
| LIFECYCLE | 0/208 | 133/208 | 0/208 |
| REF | 0/9 | 0/9 | 0/9 |
| SCOPE | 0/170 | 0/170 | 0/170 |
| SUPERSEDE | 0/3 | 0/3 | 0/3 |

## Latency and burden

- baseline: mean 0.009 ms, p95 0.001 ms per decision
- b1: mean 2.998 ms, p95 4.782 ms per decision
- b1_calibrated: mean 2.048 ms, p95 4.423 ms per decision
- b1_subprocess: mean 104.99 ms, p95 110.482 ms per decision
- b1 fabricated fields: 768 across 384 decisions (schema-required fields with no native basis)
- b1 mean request size: 2572 bytes

## Disagreements (one arm holds, the other does not)

- LIFECYCLE|clean|b1_only: 133
- SUPERSEDE|defective|b1_only: 1
