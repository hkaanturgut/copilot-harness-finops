#!/usr/bin/env sh
# One-time: lets GitHub Actions run the evals with OIDC (no secrets).
# Uses a user-assigned managed identity, so no Entra app-registration rights
# are needed (many tenants block those). Trusts this repo's main branch and
# pull requests, and grants ONLY "Foundry User" on the Foundry project.
# Then stores the IDs as GitHub repo variables (identifiers, not secrets).
#
# Needs: az signed in with rights to create resources in the resource group and
# assign roles on the project, azd env from `azd up`, gh signed in to the repo owner.
set -eu

repo="${1:-hkaanturgut/copilot-harness-finops}"
rg="$(azd env get-value AZURE_RESOURCE_GROUP)"
loc="$(azd env get-value AZURE_LOCATION)"
project_id="$(azd env get-value AZURE_AI_PROJECT_ID)"
endpoint="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT)"
foundry_user="53ca6127-db72-4b80-b1b0-d745d6d5456d"  # role GUID; display names are being renamed
name="id-gh-${repo#*/}-evals"

az identity create -g "$rg" -n "$name" -l "$loc" -o none --only-show-errors
client_id="$(az identity show -g "$rg" -n "$name" --query clientId -o tsv)"
principal_id="$(az identity show -g "$rg" -n "$name" --query principalId -o tsv)"

for pair in "main:repo:${repo}:ref:refs/heads/main" "pr:repo:${repo}:pull_request"; do
  az identity federated-credential create -g "$rg" --identity-name "$name" -n "gh-${pair%%:*}" \
    --issuer https://token.actions.githubusercontent.com --subject "${pair#*:}" \
    --audiences api://AzureADTokenExchange -o none --only-show-errors
done

az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type ServicePrincipal \
  --role "$foundry_user" --scope "$project_id" -o none --only-show-errors

gh variable set AZURE_CLIENT_ID --repo "$repo" --body "$client_id"
gh variable set AZURE_TENANT_ID --repo "$repo" --body "$(az account show --query tenantId -o tsv)"
gh variable set AZURE_SUBSCRIPTION_ID --repo "$repo" --body "$(az account show --query id -o tsv)"
gh variable set FOUNDRY_PROJECT_ENDPOINT --repo "$repo" --body "$endpoint"
echo "Done. Role propagation can take a few minutes before the first CI run."
