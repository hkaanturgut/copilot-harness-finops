# Infrastructure

The `microsoft.foundry` azd provider generates and deploys the Foundry account, project and model deployment from `azure.yaml`. No Bicep is needed here.

Everything the provider does not cover is in `scripts/postprovision.sh` (App Insights connection, egress RAI policy) and `scripts/assign-agent-role.sh` (agent identity role).
