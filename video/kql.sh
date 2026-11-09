#!/bin/zsh
# Run KQL against the project's App Insights (last 3 days) and print a table.
# Masks the Foundry account and App Insights names so recordings don't leak them.
set -eu
rg="$(azd env get-value AZURE_RESOURCE_GROUP)"
account="$(azd env get-value AZURE_AI_ACCOUNT_NAME)"
appi="$(az resource list -g "$rg" --resource-type Microsoft.Insights/components --query '[0].name' -o tsv)"
az monitor app-insights query -g "$rg" --app "$appi" --offset 3d --analytics-query "$1" -o json 2>/dev/null |
  MASK_ACCOUNT="$account" MASK_APPI="$appi" python3 -c '
import json, os, re, sys
t = json.load(sys.stdin)["tables"][0]
cols = [c["name"] for c in t["columns"]]
guid = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
def mask(s):
    s = s.replace(os.environ["MASK_ACCOUNT"], "<account>").replace(os.environ["MASK_APPI"], "<app-insights>")
    return guid.sub("<guid>", s)
rows = [[mask("%.0f" % v if isinstance(v, float) else str(v)) for v in r] for r in t["rows"]]
w = [max(len(x) for x in [c] + [r[i] for r in rows]) for i, c in enumerate(cols)]
print("  ".join(c.ljust(w[i]) for i, c in enumerate(cols)))
print("  ".join("-" * x for x in w))
for r in rows:
    print("  ".join(c.ljust(w[i]) for i, c in enumerate(r)))
'
