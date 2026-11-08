#!/usr/bin/env sh
# One-time: lets GitHub Actions run the evals with OIDC (no secrets).
# Creates an Entra app + service principal, trusts this repo's main branch and
# pull requests, and grants ONLY "Foundry User" on the Foundry project.
# Then stores the IDs as GitHub repo variables (they are identifiers, not secrets).
#
# Needs: az (signed in, permission to create app registrations and assign roles
# on the project), azd env from `azd up`, gh signed in to the repo owner.
set -eu

repo="${1:-hkaanturgut/copilot-harness-finops}"
project_id="$(azd env get-value AZURE_AI_PROJECT_ID)"
endpoint="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT)"
foundry_user="53ca6127-db72-4b80-b1b0-d745d6d5456d"  # role GUID; display names are being renamed

app_id="$(az ad app create --display-name "gh-${repo#*/}-evals" --query appId -o tsv)"
az ad sp create --id "$app_id" -o none 2>/dev/null || true
sp_id="$(az ad sp show --id "$app_id" --query id -o tsv)"

for pair in "main:repo:${repo}:ref:refs/heads/main" "pr:repo:${repo}:pull_request"; do
  az ad app federated-credential create --id "$app_id" -o none --parameters \
    "{\"name\":\"gh-${pair%%:*}\",\"issuer\":\"https://token.actions.githubusercontent.com\",\"subject\":\"${pair#*:}\",\"audiences\":[\"api://AzureADTokenExchange\"]}"
done

az role assignment create --assignee-object-id "$sp_id" --assignee-principal-type ServicePrincipal \
  --role "$foundry_user" --scope "$project_id" -o none

gh variable set AZURE_CLIENT_ID --repo "$repo" --body "$app_id"
gh variable set AZURE_TENANT_ID --repo "$repo" --body "$(az account show --query tenantId -o tsv)"
gh variable set AZURE_SUBSCRIPTION_ID --repo "$repo" --body "$(az account show --query id -o tsv)"
gh variable set FOUNDRY_PROJECT_ENDPOINT --repo "$repo" --body "$endpoint"
echo "Done. Role propagation can take a few minutes before the first CI run."
