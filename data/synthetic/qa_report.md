# Phase 5 QA report

## Checks run

| check | findings |
|---|---|
| invalid_geometry | 0 |
| overlap | 77 |
| boundary_conflict | 84 |
| duplicate_claim | 36 |
| data_integrity | 0 |
| low_confidence_confirmation | 0 |

## Adjudication queue

| category | severity | blocking | count |
|---|---|---|---|
| boundary_conflict | medium | True | 84 |
| duplicate_claim | high | True | 36 |
| overlap | high | True | 77 |

**Total findings: 197** (197 blocking, 0 informational)

## Coverage (not a finding, a metric)

- Evidence photo on file for validated STRs: 3/195 (2%)
