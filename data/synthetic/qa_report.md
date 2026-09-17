# Phase 5 QA report

## Checks run

| check | findings |
|---|---|
| invalid_geometry | 0 |
| overlap | 22 |
| boundary_conflict | 219 |
| duplicate_claim | 14 |
| data_integrity | 0 |
| low_confidence_confirmation | 0 |

## Adjudication queue

| category | severity | blocking | count |
|---|---|---|---|
| boundary_conflict | medium | True | 219 |
| duplicate_claim | high | True | 14 |
| overlap | high | True | 22 |

**Total findings: 255** (255 blocking, 0 informational)

## Coverage (not a finding, a metric)

- Evidence photo on file for validated STRs: 2/468 (0%)
