# Governed FinOps analyst on the Microsoft Copilot harness

A prompt agent on the **Microsoft Copilot harness** in Foundry Agent Service (public preview, Oct 2026) that reviews a weekly Azure cost export, flags anomalies, and returns a manager summary, a JSON block and a PNG chart.

The point isn't the agent. It's what an enterprise platform team would ask for before letting an agent with a **shell** near their data:

| Concern | What this repo does |
|---|---|
| Infrastructure as code | One `azd up`. The `microsoft.foundry` provider creates the project and model; hooks cover the rest. |
| Least-privilege tools | Only `filesystem_read`, `filesystem_write` and `shell`. Web and subagents are off. |
| Network egress | RAI policy, **default Deny**, Enforced. Allow-list: PyPI and this project's App Insights. Everything else gets HTTP 403. |
| Identity | Entra only. The agent's own identity gets **Foundry User** after deploy (it doesn't exist before). CI uses OIDC (user-assigned managed identity) with Foundry User only: it can run evals, not deploy. |
| Observability | App Insights connected to the project: server-side traces, including one span per egress decision. |
| Quality gate | 15 synthetic cost exports with seeded anomalies. CI fails on recall < 0.90, precision < 0.80, week total off by > 1%, no chart, or egress not blocked. |
| Cost | Budget alert on the resource group. Harness runtime is free until 2026-12-01, then USD 0.0994/vCPU-hour + 0.0118/GiB-hour plus model tokens. |

## Architecture

```mermaid
flowchart LR
  user[Engineer / CI] -->|Entra token| ep[Agent endpoint<br/>finops-analyst]
  subgraph Foundry project
    ep --> harness[Copilot harness<br/>agent loop + sandbox]
    harness -->|tokens| model[gpt-5.4-mini]
    harness -->|read/write/shell| sandbox[(Sandbox workspace<br/>CSV in, PNG out)]
    harness --> files[Foundry Files]
  end
  sandbox -->|egress policy: Deny by default| internet((Internet))
  sandbox -->|allowed| pypi[pypi.org]
  harness -. traces .-> appi[App Insights]
```

## Run it

Prereqs: `azd` 1.37+, the `microsoft.foundry` azd extension, Azure CLI, Python 3.9+, a subscription in a [supported region](https://learn.microsoft.com/azure/foundry/agents/concepts/limits-quotas-regions#microsoft-copilot-harness-preview).

```bash
azd extension install microsoft.foundry
export AZD_ALPHA_ENABLE_AGENTS_MANAGED_HARNESS=true   # every shell, during the preview
azd auth login
azd env new finops-demo --location canadacentral
azd up

python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python chat.py sample-data/cost-export-2026-11-01.csv --prompt "Review this week's cost export."
```

Try the egress policy:

```bash
python chat.py sample-data/cost-export-2026-11-01.csv --prompt \
  'Use shell to run: curl -s -o /dev/null -w "%{http_code}" https://example.com'
# -> 403
```

Run the eval gate:

```bash
python evals/generate_data.py   # optional: regenerate the 15 cases + sample
python evals/run_evals.py       # writes evals/results/latest.md
```

CI setup (one time, creates a user-assigned managed identity with a GitHub federated credential; no app-registration rights needed): `./scripts/setup-github-oidc.sh`.

Tear down: `azd down --purge --force`.

## Detection rule

Deterministic on purpose, so the evals have a ground truth. Over 28 days of daily cost per resource, the last 7 days are the analysis week:

- `spike` / `step_change`: first day > 2x the resource's baseline median **and** ≥ USD 25 above it (`step_change` if it stays there).
- `new_resource`: no baseline cost and > USD 100 in the analysis week.

## Results

Latest run (2026-11-08, agent v2, gpt-5.4-mini, 3 parallel workers): **PASS**. Full table in [`evals/results/latest.md`](evals/results/latest.md).

| Metric | Result |
|---|---|
| Recall / precision | **1.00 / 1.00** (26 of 26 seeded anomalies, 0 false positives) |
| Week total within 1% | 15/15 |
| Chart returned | 15/15 |
| Egress to example.com | HTTP 403 |
| Median time per case | 58 s |

Honest history: the three runs before this one failed. None of the failures were wrong detections. The causes were model rate limits, a response stuck `in_progress`, the final message arriving after `completed`, the chart upload swallowing the final answer, and my own client's token handling. Each one is a fix in this repo and a lesson below. One green run isn't proof of stability, so the gate keeps running in CI.

## Things I learned (preview, Nov 2026)

- **Egress decision spans do show up.** Each outbound request is a dependency span named `Network egress decision: Allow|Deny <METHOD> <host>`, which turns Audit into a simple KQL query.
- **Default Deny blocks the harness's own telemetry** to App Insights until you allow the project's ingestion and live-metrics hosts. `scripts/postprovision.sh` reads them from the connection string.
- **Shell calls are traced** as `execute_tool bash` spans next to the model calls and `session.provisioning` (about 130 ms at the median).
- **The sandbox, measured from inside:** 1 vCPU, about 2.2 GiB RAM, 16 GB disk, Debian 12, root. That's about USD 0.125/hour alive after 2026-12-01.
- **Don't end on a tool call.** If uploading the chart is the agent's last step, the final answer can be replaced by "The agent generated the following files, which are attached." Instruct it to upload first and answer last.
- **`completed` can come before the final message.** Re-read the response for up to about 90 s before treating a missing answer as a failure.
- **Plan capacity for evals.** 50K TPM rate-limited three parallel agent runs. `azd deploy` doesn't change an existing deployment's capacity; `az cognitiveservices account deployment create --sku-capacity` does.
- **Put the logic in code the agent runs**, not in the agent's head. Asking for one script that applies the rule and copying its output verbatim removed the misses.
- **GitHub OIDC subjects include IDs now**: `repo:owner@<id>/name@<id>:ref:refs/heads/main`. A federated credential with the plain `repo:owner/name:...` subject fails with AADSTS700213. The setup script reads the IDs from the GitHub API.
- **Still unverified:** private networking with the harness, a region-bound model deployment (this uses GlobalStandard), and the sandbox idle timeout.

## Credits

Started from Microsoft's [`csv-chart-analyst`](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/cli/prompt-agents/microsoft-copilot-harness/csv-chart-analyst) sample (MIT). Docs: [Copilot harness how-to](https://learn.microsoft.com/azure/foundry/agents/how-to/use-tools-skills-copilot-harness), [announcement](https://devblogs.microsoft.com/foundry/microsoft-copilot-harness-in-foundry/).
