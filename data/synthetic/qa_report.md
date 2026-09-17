# Phase 5 QA report

## Checks run

| check | findings |
|---|---|
| invalid_geometry | 0 |
| overlap | 0 |
| boundary_conflict | 5 |
| duplicate_claim | 37 |
| data_integrity | 0 |
| low_confidence_confirmation | 77 |

## Adjudication queue

| category | severity | blocking | count |
|---|---|---|---|
| boundary_conflict | medium | True | 5 |
| duplicate_claim | high | True | 37 |
| low_confidence_confirmation | low | False | 77 |

**Total findings: 119** (42 blocking, 77 informational)

## Coverage (not a finding, a metric)

- Evidence photo on file for validated STRs: 4/379 (1%)
