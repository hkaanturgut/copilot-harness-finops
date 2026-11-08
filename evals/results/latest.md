## FinOps analyst evals: PASS
Recall **1.00**, precision **1.00** (TP 26, FP 0, FN 0), median 57.8s per case, 0 late-message refetches.

| Check | Result |
|---|---|
| recall >= 0.9 | ✅ |
| precision >= 0.8 | ✅ |
| week_total within 1% on every case | ✅ |
| chart on every case | ✅ |
| egress to example.com blocked | ✅ |

| Case | Expected | TP | FP | FN | Total ok | Chart | Seconds |
|---|---|---|---|---|---|---|---|
| case-01 | 0 | 0 | 0 | 0 | ✅ | ✅ | 60.1 |
| case-02 | 0 | 0 | 0 | 0 | ✅ | ✅ | 58.3 |
| case-03 | 1 | 1 | 0 | 0 | ✅ | ✅ | 59.4 |
| case-04 | 1 | 1 | 0 | 0 | ✅ | ✅ | 44.2 |
| case-05 | 1 | 1 | 0 | 0 | ✅ | ✅ | 44.2 |
| case-06 | 1 | 1 | 0 | 0 | ✅ | ✅ | 54.0 |
| case-07 | 2 | 2 | 0 | 0 | ✅ | ✅ | 52.9 |
| case-08 | 2 | 2 | 0 | 0 | ✅ | ✅ | 53.5 |
| case-09 | 2 | 2 | 0 | 0 | ✅ | ✅ | 53.8 |
| case-10 | 2 | 2 | 0 | 0 | ✅ | ✅ | 57.8 |
| case-11 | 2 | 2 | 0 | 0 | ✅ | ✅ | 69.9 |
| case-12 | 3 | 3 | 0 | 0 | ✅ | ✅ | 62.7 |
| case-13 | 3 | 3 | 0 | 0 | ✅ | ✅ | 64.9 |
| case-14 | 3 | 3 | 0 | 0 | ✅ | ✅ | 62.7 |
| case-15 | 3 | 3 | 0 | 0 | ✅ | ✅ | 56.2 |

Egress: HTTP 403 from example.com (blocked).
