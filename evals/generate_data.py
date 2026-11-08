"""Generate synthetic Azure cost exports with seeded anomalies.

Each case is 28 days of daily cost per resource: 21 baseline days plus a
7-day analysis week. Anomalies are only seeded in the analysis week, and
baseline noise stays within +/-15% so it never trips the detection rule in
the agent instructions (cost > 2x baseline median and > USD 25 above it).

Usage: python evals/generate_data.py            # writes evals/cases/ and sample-data/
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "evals" / "cases"
SAMPLE = ROOT / "sample-data"
START = date(2026, 10, 5)
DAYS = 28
BASELINE_DAYS = 21

# (resource_group, resource, service, meter, base daily USD)
RESOURCES = [
    ("rg-web-prod", "app-web-prod", "Azure App Service", "P1v3 App Service Hours", 62.0),
    ("rg-web-prod", "sql-web-prod", "SQL Database", "vCore", 88.0),
    ("rg-web-prod", "fd-web-prod", "Azure Front Door", "Data Transfer Out", 21.0),
    ("rg-data-prod", "adf-ingest-prod", "Azure Data Factory v2", "Orchestration Activity Run", 34.0),
    ("rg-data-prod", "st-lake-prod", "Storage", "Hot LRS Data Stored", 47.0),
    ("rg-data-prod", "dbw-analytics-prod", "Azure Databricks", "Premium All-purpose Compute DBU", 140.0),
    ("rg-platform", "aks-platform", "Azure Kubernetes Service", "Standard Uptime SLA", 73.0),
    ("rg-platform", "vmss-aks-nodes", "Virtual Machines", "D4s v5", 156.0),
    ("rg-platform", "log-platform", "Log Analytics", "Analytics Logs Data Ingestion", 39.0),
    ("rg-platform", "kv-platform", "Key Vault", "Operations", 3.5),
    ("rg-ai-dev", "aoai-dev", "Foundry Models", "gpt-5.4-mini Input Tokens", 18.0),
    ("rg-ai-dev", "srch-dev", "Azure AI Search", "Standard S1 Unit", 8.2),
]
NEW_RESOURCES = [
    ("rg-ai-dev", "vm-gpu-experiment", "Virtual Machines", "NC24ads A100 v4", 88.0),
    ("rg-data-prod", "synw-adhoc", "Azure Synapse Analytics", "Serverless SQL TB Processed", 45.0),
    ("rg-web-prod", "redis-cache-new", "Redis Cache", "P2 Cache Instance", 31.0),
]


def day(i: int) -> str:
    return (START + timedelta(days=i)).isoformat()


def make_case(seed: int, n_anomalies: int) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    costs = {r[1]: [r[4] * rng.uniform(0.85, 1.15) for _ in range(DAYS)] for r in RESOURCES}
    meta = {r[1]: r for r in RESOURCES}
    truth: list[dict] = []

    kinds = rng.sample(["spike", "step_change", "new_resource", "spike", "step_change"], n_anomalies)
    candidates = [r for r in RESOURCES if r[4] >= 30]  # big enough to clear the 2x and USD 25 rule
    rng.shuffle(candidates)
    for kind in kinds:
        first = rng.randint(BASELINE_DAYS, DAYS - 2)
        if kind == "new_resource":
            rg, name, svc, meter, base = rng.choice([n for n in NEW_RESOURCES if n[1] not in costs])
            meta[name] = (rg, name, svc, meter, base)
            costs[name] = [0.0] * DAYS
            for i in range(first, DAYS):
                costs[name][i] = base * rng.uniform(0.9, 1.1)
            # make sure the week total clears USD 100
            if sum(costs[name][BASELINE_DAYS:]) < 110:
                costs[name][first] += 110
        else:
            rg, name, svc, meter, base = candidates.pop()
            factor = rng.uniform(4.0, 7.0) if kind == "spike" else rng.uniform(2.8, 3.4)
            last = first if kind == "spike" else DAYS - 1
            for i in range(first, last + 1):
                costs[name][i] = base * factor * rng.uniform(0.95, 1.05)
        truth.append({"resource": name, "resource_group": rg, "date": day(first), "type": kind})

    rows = []
    for name, series in costs.items():
        rg, _, svc, meter, _ = meta[name]
        for i, c in enumerate(series):
            if c > 0:
                rows.append({
                    "Date": day(i), "SubscriptionName": "sub-contoso-prod", "ResourceGroup": rg,
                    "ResourceName": name, "ServiceName": svc, "MeterName": meter,
                    "CostInBillingCurrency": f"{c:.2f}", "BillingCurrency": "USD",
                })
    rows.sort(key=lambda r: (r["Date"], r["ResourceGroup"], r["ResourceName"]))
    week_total = round(sum(float(r["CostInBillingCurrency"]) for r in rows if r["Date"] >= day(BASELINE_DAYS)), 2)
    return rows, {
        "analysis_start": day(BASELINE_DAYS), "analysis_end": day(DAYS - 1),
        "week_total": week_total, "anomalies": sorted(truth, key=lambda t: t["resource"]),
    }


def write(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    SAMPLE.mkdir(parents=True, exist_ok=True)
    # 15 cases: 2 clean, the rest 1-3 anomalies
    plan = [0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3]
    for i, n in enumerate(plan, start=1):
        rows, truth = make_case(seed=1000 + i, n_anomalies=n)
        write(rows, CASES / f"case-{i:02d}.csv")
        (CASES / f"case-{i:02d}.json").write_text(json.dumps(truth, indent=2) + "\n")
    rows, truth = make_case(seed=42, n_anomalies=2)
    write(rows, SAMPLE / "cost-export-2026-11-01.csv")
    (SAMPLE / "cost-export-2026-11-01.truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    print(f"Wrote {len(plan)} cases to {CASES} and a sample export to {SAMPLE}")


if __name__ == "__main__":
    main()
