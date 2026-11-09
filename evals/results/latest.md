## FinOps analyst evals: PASS
Answered 15/15. On answered cases: recall **1.00**, precision **1.00** (TP 26, FP 0, FN 0), median 72.5s per case, 0 late-message refetches.

| Check | Result |
|---|---|
| answered >= 80% of cases (15/15) | ✅ |
| recall >= 0.9 | ✅ |
| precision >= 0.8 | ✅ |
| week_total within 1% on every answered case | ✅ |
| chart on every answered case | ✅ |
| egress to example.com blocked | ✅ |

| Case | Expected | TP | FP | FN | Total ok | Chart | Seconds |
|---|---|---|---|---|---|---|---|
| case-01 | 0 | 0 | 0 | 0 | ✅ | ✅ | 72.5 |
| case-02 | 0 | 0 | 0 | 0 | ✅ | ✅ | 79.0 |
| case-03 | 1 | 1 | 0 | 0 | ✅ | ✅ | 60.2 |
| case-04 | 1 | 1 | 0 | 0 | ✅ | ✅ | 69.2 |
| case-05 | 1 | 1 | 0 | 0 | ✅ | ✅ | 58.1 |
| case-06 | 1 | 1 | 0 | 0 | ✅ | ✅ | 76.6 |
| case-07 | 2 | 2 | 0 | 0 | ✅ | ✅ | 109.0 |
| case-08 | 2 | 2 | 0 | 0 | ✅ | ✅ | 63.5 |
| case-09 | 2 | 2 | 0 | 0 | ✅ | ✅ | 56.7 |
| case-10 | 2 | 2 | 0 | 0 | ✅ | ✅ | 100.7 |
| case-11 | 2 | 2 | 0 | 0 | ✅ | ✅ | 97.9 |
| case-12 | 3 | 3 | 0 | 0 | ✅ | ✅ | 56.4 |
| case-13 | 3 | 3 | 0 | 0 | ✅ | ✅ | 76.9 |
| case-14 | 3 | 3 | 0 | 0 | ✅ | ✅ | 66.9 |
| case-15 | 3 | 3 | 0 | 0 | ✅ | ✅ | 75.2 |

Egress: HTTP 403 from example.com (blocked).
