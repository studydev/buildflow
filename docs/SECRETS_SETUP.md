# Azure Key Vault Secrets Setup

This document describes how to set up production secrets in Azure Key Vault for the BuildFlow application.

## Prerequisites

- Azure CLI installed and logged in
- Access to the Azure subscription
- Key Vault created (via `infra/main.bicep` deployment)

## Required Secrets

The following secrets must be configured in Key Vault:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `jwt-secret` | JWT signing secret (min 32 characters) | ✅ Yes |
| `cosmos-key` | Cosmos DB primary key | ✅ Yes (auto-created) |
| `github-token` | GitHub Personal Access Token | ⚠️ Optional |
| `azure-openai-key` | Azure OpenAI API key | ⚠️ Optional |

## Setup Commands

### 1. Get Key Vault Name

```bash
# List Key Vaults in resource group
az keyvault list --resource-group buildflow-rg --query "[].name" -o tsv
```

### 2. Set JWT Secret

```bash
# Generate a secure random secret
JWT_SECRET=$(openssl rand -base64 32)

# Store in Key Vault
az keyvault secret set \
  --vault-name <your-keyvault-name> \
  --name jwt-secret \
  --value "$JWT_SECRET"
```

### 3. Set GitHub Token (Optional)

```bash
# Create a GitHub Personal Access Token with 'repo' scope
# https://github.com/settings/tokens

az keyvault secret set \
  --vault-name <your-keyvault-name> \
  --name github-token \
  --value "<your-github-token>"
```

### 4. Set Azure OpenAI Key (Optional)

```bash
az keyvault secret set \
  --vault-name <your-keyvault-name> \
  --name azure-openai-key \
  --value "<your-openai-key>"
```

## Verify Secrets

```bash
# List all secrets in Key Vault
az keyvault secret list --vault-name <your-keyvault-name> --query "[].name" -o tsv

# Verify a secret exists (shows metadata only)
az keyvault secret show --vault-name <your-keyvault-name> --name jwt-secret --query "name"
```

## Grant Access to Container App

The managed identity created by the Bicep template automatically has access to read secrets.

To manually grant access:

```bash
# Get managed identity principal ID
IDENTITY_ID=$(az identity show \
  --resource-group buildflow-rg \
  --name id-buildflow-dev-<unique-suffix> \
  --query principalId -o tsv)

# Grant Key Vault Secrets User role
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee $IDENTITY_ID \
  --scope /subscriptions/<sub-id>/resourceGroups/buildflow-rg/providers/Microsoft.KeyVault/vaults/<keyvault-name>
```

## Rotate Secrets

To rotate a secret:

1. Generate new secret value
2. Update in Key Vault: `az keyvault secret set ...`
3. Restart Container App to pick up new secret: `az containerapp revision restart ...`

## Security Best Practices

- ✅ Use managed identity for secret access (no stored credentials)
- ✅ Enable soft delete on Key Vault
- ✅ Rotate secrets regularly
- ✅ Use RBAC authorization (not access policies)
- ✅ Enable diagnostic logging on Key Vault
- ❌ Never commit secrets to source control
- ❌ Never expose secrets in logs or error messages
