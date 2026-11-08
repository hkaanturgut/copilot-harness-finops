#!/usr/bin/env sh
# Runs after `azd provision`. Idempotent.
#  1. Log Analytics + Application Insights, connected to the Foundry project (server-side tracing).
#  2. An RAI policy with a network egress control: deny by default, allow PyPI only.
#  3. Stores RAI_POLICY_ID in the azd env so the agent deploy attaches the policy.
set -eu

sub="$(azd env get-value AZURE_SUBSCRIPTION_ID)"
rg="$(azd env get-value AZURE_RESOURCE_GROUP)"
loc="$(azd env get-value AZURE_LOCATION)"
env_name="$(azd env get-value AZURE_ENV_NAME)"
account="$(azd env get-value AZURE_AI_ACCOUNT_NAME)"
project="$(azd env get-value AZURE_AI_PROJECT_NAME)"
egress_mode="${EGRESS_MODE:-Enforced}"
arm="https://management.azure.com/subscriptions/${sub}/resourceGroups/${rg}/providers/Microsoft.CognitiveServices/accounts/${account}"

echo "Observability: Log Analytics + Application Insights"
law_id="$(az monitor log-analytics workspace create -g "$rg" -n "log-${env_name}" -l "$loc" \
  --retention-time 30 --query id -o tsv --only-show-errors)"
appi_json="$(az monitor app-insights component create -g "$rg" -a "appi-${env_name}" -l "$loc" \
  --workspace "$law_id" --kind web --application-type web --only-show-errors -o json)"
appi_id="$(printf '%s' "$appi_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
appi_cs="$(printf '%s' "$appi_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["connectionString"])')"

echo "Connecting Application Insights to project ${project}"
az rest --method put --only-show-errors -o none \
  --url "${arm}/projects/${project}/connections/appinsights?api-version=2025-06-01" \
  --body "$(python3 -c 'import json,sys; print(json.dumps({"properties": {
      "category": "AppInsights", "target": sys.argv[1], "authType": "ApiKey",
      "isSharedToAll": False, "credentials": {"key": sys.argv[2]},
      "metadata": {"ApiType": "Azure", "ResourceId": sys.argv[1]}}}))' "$appi_id" "$appi_cs")"

# Hosts the harness itself needs for telemetry to this project's App Insights.
# Found with the egress decision spans: deny-by-default otherwise blocks them.
ingest_host="$(printf '%s' "$appi_cs" | tr ';' '\n' | sed -n 's#^IngestionEndpoint=https://\([^/]*\).*#\1#p')"
live_host="$(printf '%s' "$appi_cs" | tr ';' '\n' | sed -n 's#^LiveEndpoint=https://\([^/]*\).*#\1#p')"

echo "Egress policy (${egress_mode}, default Deny, allow PyPI + ${ingest_host} + ${live_host})"
rules="$(python3 -c 'import json,sys
hosts = [("allow-pypi", "pypi.org"), ("allow-pypi-files", "files.pythonhosted.org"),
         ("allow-appinsights-ingest", sys.argv[1]), ("allow-appinsights-live", sys.argv[2])]
print(json.dumps([{"name": n, "ruleType": "Fqdn", "match": {"host": h}, "action": {"actionType": "Allow"}}
                  for n, h in hosts if h]))' "$ingest_host" "$live_host")"
az rest --method put --only-show-errors -o none \
  --url "${arm}/raiPolicies/finops-egress?api-version=2026-05-15-preview" \
  --body "{\"properties\":{\"mode\":\"Blocking\",\"basePolicyName\":\"Microsoft.DefaultV2\",\"contentFilters\":[],
    \"egressPolicy\":{\"mode\":\"${egress_mode}\",\"defaultAction\":\"Deny\",\"rules\":${rules}}}}"

azd env set RAI_POLICY_ID "/subscriptions/${sub}/resourceGroups/${rg}/providers/Microsoft.CognitiveServices/accounts/${account}/raiPolicies/finops-egress"
echo "RAI_POLICY_ID set."
