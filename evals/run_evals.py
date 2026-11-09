"""Eval gate for the FinOps analyst agent.

Runs every case in evals/cases/ against the deployed agent, compares the JSON
block with the seeded ground truth, and checks that egress is blocked.

Pass bar (override with flags): recall >= 0.90, precision >= 0.80,
week_total within 1% on every case, a chart on every case, egress blocked.

Usage: python evals/run_evals.py [--workers 5] [--cases case-01,case-02]
Needs FOUNDRY_PROJECT_ENDPOINT (env or azd env) and an `az login` session.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from chat import FoundryClient, azd_env_value, response_text_and_files  # noqa: E402

CASES = ROOT / "evals" / "cases"
RESULTS = ROOT / "evals" / "results"
PROMPT = "Review this week's cost export."
REFETCHES: list[str] = []
EGRESS_PROMPT = (
    "Network test only, do not analyze the CSV. Use shell to run exactly: "
    'curl -sS -m 15 -o /dev/null -w "%{http_code}" https://example.com ; echo " exit=$?" '
    "and reply with only the raw output inside a ```text block."
)


def ask(client: FoundryClient, csv_path: Path, prompt: str, attempts: int = 3) -> tuple[str, list[dict], float]:
    """One fresh conversation per call. Retries model rate limits with backoff."""
    for attempt in range(attempts):
        try:
            return _ask_once(client, csv_path, prompt)
        except TimeoutError:
            # Preview: a response occasionally stays in_progress. Retry once in a new conversation.
            if attempt >= 1:
                raise
            print(f"[{csv_path.stem}] response stuck in_progress, retrying", file=sys.stderr, flush=True)
        except RuntimeError as exc:
            if "rate_limit" not in str(exc) or attempt == attempts - 1:
                raise
            time.sleep(30 * (attempt + 1))
    raise AssertionError("unreachable")


def _ask_once(client: FoundryClient, csv_path: Path, prompt: str) -> tuple[str, list[dict], float]:
    started = time.monotonic()
    file_id = client.upload_csv(csv_path)
    conversation = client.create_conversation()
    response = client.respond(conversation, prompt, file_id)
    if response.get("status") != "completed":
        raise RuntimeError(json.dumps(response.get("error") or response.get("status")))
    text, files = response_text_and_files(response, excluded_file_ids={file_id})
    # Preview: a response can report `completed` before its final message is visible.
    # Re-read it a few times before giving up, and count how often that happens.
    for _ in range(12):  # up to ~90s
        if "```json" in text or "Network test" in prompt:
            break
        REFETCHES.append(response["id"])
        time.sleep(7.5)
        response = client.request(
            "GET",
            f"{client.agent_endpoint}/responses/{response['id']}?api-version=v1",
            headers=client.feature_headers,
        ).json()
        text, files = response_text_and_files(response, excluded_file_ids={file_id})
    return text, files, time.monotonic() - started


def parse_json_block(text: str) -> dict | None:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def run_case(client: FoundryClient, name: str) -> dict:
    result = _run_case(client, name)
    status = result.get("error") or f"tp={result['tp']} fp={result['fp']} fn={result['fn']} {result.get('seconds')}s"
    print(f"[{name}] {status}", file=sys.stderr, flush=True)
    return result


def _run_case(client: FoundryClient, name: str) -> dict:
    truth = json.loads((CASES / f"{name}.json").read_text())
    result: dict = {"case": name, "expected": len(truth["anomalies"])}
    try:
        text, files, seconds = ask(client, CASES / f"{name}.csv", PROMPT)
    except Exception as exc:  # report, don't crash the whole run
        return {**result, "error": str(exc)[:300], "tp": 0, "fp": 0, "fn": len(truth["anomalies"])}
    (RESULTS / "raw").mkdir(parents=True, exist_ok=True)
    (RESULTS / "raw" / f"{name}.md").write_text(text)
    data = parse_json_block(text) or {}
    predicted = {(a.get("resource"), a.get("date")) for a in data.get("anomalies", [])}
    expected = {(a["resource"], a["date"]) for a in truth["anomalies"]}
    expected_types = {(a["resource"], a["date"]): a["type"] for a in truth["anomalies"]}
    types_ok = all(
        a.get("type") == expected_types.get((a.get("resource"), a.get("date")))
        for a in data.get("anomalies", []) if (a.get("resource"), a.get("date")) in expected
    )
    total = data.get("week_total")
    total_ok = isinstance(total, (int, float)) and abs(total - truth["week_total"]) <= 0.01 * truth["week_total"]
    return {
        **result,
        "seconds": round(seconds, 1),
        "json_ok": bool(data),
        "tp": len(predicted & expected),
        "fp": len(predicted - expected),
        "fn": len(expected - predicted),
        "types_ok": types_ok,
        "week_total": total,
        "week_total_expected": truth["week_total"],
        "total_ok": total_ok,
        "chart_ok": any(f["filename"].lower().endswith(".png") for f in files),
        "missed": sorted(map(list, expected - predicted)),
        "extra": sorted(map(list, predicted - expected)),
    }


def run_egress(client: FoundryClient) -> dict:
    try:
        text, _, seconds = ask(client, CASES / "case-01.csv", EGRESS_PROMPT)
    except Exception as exc:
        return {"blocked": False, "error": str(exc)[:300]}
    code = re.search(r"\b(\d{3})\s*exit=", text)
    status = code.group(1) if code else None
    return {"blocked": status is not None and status != "200", "http_code": status,
            "output": text.strip()[-200:], "seconds": round(seconds, 1)}


def main() -> int:
    os.environ.setdefault("RESPONSE_TIMEOUT_SECONDS", "300")
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--cases", default="", help="comma-separated case names; default all")
    parser.add_argument("--min-recall", type=float, default=0.90)
    parser.add_argument("--min-precision", type=float, default=0.80)
    args = parser.parse_args()

    names = args.cases.split(",") if args.cases else sorted(p.stem for p in CASES.glob("case-*.csv"))
    client = FoundryClient(os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or azd_env_value("FOUNDRY_PROJECT_ENDPOINT"))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        egress_future = pool.submit(run_egress, client)
        cases = list(pool.map(lambda n: run_case(client, n), names))
        egress = egress_future.result()

    tp = sum(c["tp"] for c in cases)
    fp = sum(c["fp"] for c in cases)
    fn = sum(c["fn"] for c in cases)
    recall = tp / (tp + fn) if tp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    checks = {
        f"recall >= {args.min_recall}": recall >= args.min_recall,
        f"precision >= {args.min_precision}": precision >= args.min_precision,
        "week_total within 1% on every case": all(c.get("total_ok") for c in cases),
        "chart on every case": all(c.get("chart_ok") for c in cases),
        "egress to example.com blocked": egress.get("blocked", False),
    }
    passed = all(checks.values())
    summary = {
        "passed": passed, "recall": round(recall, 3), "precision": round(precision, 3),
        "tp": tp, "fp": fp, "fn": fn, "checks": checks, "egress": egress, "cases": cases,
        "late_message_refetches": len(REFETCHES),
        "median_seconds": sorted(c.get("seconds", 0) for c in cases)[len(cases) // 2],
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "latest.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        f"## FinOps analyst evals: {'PASS' if passed else 'FAIL'}",
        f"Recall **{recall:.2f}**, precision **{precision:.2f}** (TP {tp}, FP {fp}, FN {fn}), "
        f"median {summary['median_seconds']}s per case, {len(REFETCHES)} late-message refetches.",
        "",
        "| Check | Result |", "|---|---|",
        *[f"| {k} | {'✅' if v else '❌'} |" for k, v in checks.items()],
        "",
        "| Case | Expected | TP | FP | FN | Total ok | Chart | Seconds |", "|---|---|---|---|---|---|---|---|",
        *[f"| {c['case']} | {c['expected']} | {c['tp']} | {c['fp']} | {c['fn']} | "
          f"{'✅' if c.get('total_ok') else '❌'} | {'✅' if c.get('chart_ok') else '❌'} | "
          f"{c.get('seconds', c.get('error', ''))} |" for c in cases],
        "",
        f"Egress: HTTP {egress.get('http_code')} from example.com ({'blocked' if egress.get('blocked') else 'NOT blocked'}).",
    ]
    report = "\n".join(lines) + "\n"
    (RESULTS / "latest.md").write_text(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(report)
    print(report)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
