// BuildFlow Infrastructure - Main Bicep Template
// Deploys Container Apps, Cosmos DB, Key Vault, and supporting resources

targetScope = 'resourceGroup'

// Parameters
@description('Environment name (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Project name used for resource naming')
param projectName string = 'buildflow'

@description('Container image for the API')
param apiImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@secure()
@description('JWT Secret for authentication')
param jwtSecret string

@secure()
@description('GitHub Token for API access')
param githubToken string = ''

@secure()
@description('Azure OpenAI Key')
param azureOpenAiKey string = ''

@description('Azure OpenAI Endpoint')
param azureOpenAiEndpoint string = ''

@description('Azure OpenAI Deployment Name')
param azureOpenAiDeployment string = ''

@secure()
@description('Azure Communication Services Connection String for OTP emails')
param acsConnectionString string = ''

@description('Azure Communication Services Sender Address for OTP emails')
param acsSenderAddress string = ''

@description('CORS allowed origins (comma-separated)')
param corsOrigins string = 'http://localhost:5173,http://localhost:3000'

@secure()
@description('YouTube Data API v3 Key')
param youtubeApiKey string = ''

@description('Dev bypass email for non-prod environments')
param devBypassEmail string = ''

@description('Enable monitoring resources (App Insights, alerts')
param enableMonitoring bool = true

@description('Enable frontend Static Web App deployment')
param enableFrontend bool = true

@description('Email for alert notifications')
param alertEmail string = ''

// Variables
var resourceSuffix = '${projectName}-${environment}-${uniqueString(resourceGroup().id)}'
// Key Vault name: alphanumeric only, 3-24 chars, start with letter, end with letter/digit
var kvUniqueSuffix = uniqueString(resourceGroup().id, projectName)
var keyVaultName = toLower(take('kv${projectName}${environment}${kvUniqueSuffix}', 24))
// Container App name: 2-32 chars, lowercase alphanumeric and hyphens, start with letter, end with alphanumeric
var shortSuffix = take(uniqueString(resourceGroup().id), 6)
var containerAppName = 'ca-${projectName}-${environment}-${shortSuffix}'
var tags = {
  project: projectName
  environment: environment
  managedBy: 'bicep'
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${resourceSuffix}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Container Apps Environment
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: 'cae-${resourceSuffix}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Cosmos DB Account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: 'cosmos-${resourceSuffix}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

// Cosmos DB Database
resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: 'buildflow'
  properties: {
    resource: {
      id: 'buildflow'
    }
  }
}

// Cosmos DB Containers
var containers = [
  { name: 'users', partitionKey: '/id' }
  { name: 'contents', partitionKey: '/id' }
  { name: 'analysis_requests', partitionKey: '/id' }
  { name: 'login_history', partitionKey: '/email' }
]

resource cosmosContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = [for container in containers: {
  parent: cosmosDatabase
  name: container.name
  properties: {
    resource: {
      id: container.name
      partitionKey: {
        paths: [container.partitionKey]
        kind: 'Hash'
      }
    }
  }
}]

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// Key Vault Secrets
resource jwtSecretKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'jwt-secret'
  properties: {
    value: jwtSecret
  }
}

resource cosmosConnectionStringKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'cosmos-connection-string'
  properties: {
    value: 'AccountEndpoint=${cosmosAccount.properties.documentEndpoint};AccountKey=${cosmosAccount.listKeys().primaryMasterKey}'
  }
}

resource githubTokenKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = if (!empty(githubToken)) {
  parent: keyVault
  name: 'github-token'
  properties: {
    value: githubToken
  }
}

resource openAiKeyKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = if (!empty(azureOpenAiKey)) {
  parent: keyVault
  name: 'azure-openai-key'
  properties: {
    value: azureOpenAiKey
  }
}

resource youtubeApiKeyKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = if (!empty(youtubeApiKey)) {
  parent: keyVault
  name: 'youtube-api-key'
  properties: {
    value: youtubeApiKey
  }
}

resource acsConnectionStringKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = if (!empty(acsConnectionString)) {
  parent: keyVault
  name: 'acs-connection-string'
  properties: {
    value: acsConnectionString
  }
}

// User Assigned Managed Identity
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${resourceSuffix}'
  location: location
  tags: tags
}

// ============================================================================
// Container Registry Module
// ============================================================================

module containerRegistry 'modules/container-registry.bicep' = {
  name: 'containerRegistryDeployment'
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    managedIdentityPrincipalId: managedIdentity.properties.principalId
  }
}

// ============================================================================
// Storage Module (moved before Container App for dependency)
// ============================================================================

module storage 'modules/storage.bicep' = {
  name: 'storageDeployment'
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    managedIdentityPrincipalId: managedIdentity.properties.principalId
  }
}

// Store Storage connection string in Key Vault
resource storageConnectionKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'storage-connection'
  properties: {
    value: storage.outputs.connectionString
  }
}

// Store Storage account name in Key Vault
resource storageAccountNameKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'storage-account-name'
  properties: {
    value: storage.outputs.storageAccountName
  }
}

// Store Storage account key in Key Vault
resource storageAccountKeyKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'storage-account-key'
  properties: {
    value: storage.outputs.primaryAccessKey
  }
}

// Key Vault Access for Managed Identity
resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Container App - API
resource apiContainerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8001
        transport: 'http'
        corsPolicy: {
          allowedOrigins: split(corsOrigins, ',')
          allowedMethods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: true
        }
      }
      secrets: concat([
        {
          name: 'jwt-secret'
          keyVaultUrl: jwtSecretKv.properties.secretUri
          identity: managedIdentity.id
        }
        {
          name: 'cosmos-connection-string'
          keyVaultUrl: cosmosConnectionStringKv.properties.secretUri
          identity: managedIdentity.id
        }
        {
          name: 'storage-connection'
          keyVaultUrl: storageConnectionKv.properties.secretUri
          identity: managedIdentity.id
        }
        {
          name: 'storage-account-name'
          keyVaultUrl: storageAccountNameKv.properties.secretUri
          identity: managedIdentity.id
        }
        {
          name: 'storage-account-key'
          keyVaultUrl: storageAccountKeyKv.properties.secretUri
          identity: managedIdentity.id
        }
      // Conditionally add ACS secret only when connection string is provided
      ], !empty(acsConnectionString) ? [
        {
          name: 'acs-connection-string'
          #disable-next-line BCP318
          keyVaultUrl: acsConnectionStringKv.properties.secretUri
          identity: managedIdentity.id
        }
      ] : [], !empty(githubToken) ? [
        {
          name: 'github-token'
          #disable-next-line BCP318
          keyVaultUrl: githubTokenKv.properties.secretUri
          identity: managedIdentity.id
        }
      ] : [], !empty(azureOpenAiKey) ? [
        {
          name: 'azure-openai-key'
          #disable-next-line BCP318
          keyVaultUrl: openAiKeyKv.properties.secretUri
          identity: managedIdentity.id
        }
      ] : [], !empty(youtubeApiKey) ? [
        {
          name: 'youtube-api-key'
          #disable-next-line BCP318
          keyVaultUrl: youtubeApiKeyKv.properties.secretUri
          identity: managedIdentity.id
        }
      ] : [], [
        {
          name: 'search-admin-key'
          keyVaultUrl: searchAdminKeyKv.properties.secretUri
          identity: managedIdentity.id
        }
      ])
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat([
            { name: 'ENV', value: environment }
            { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
            { name: 'JWT_ALGORITHM', value: 'HS256' }
            { name: 'COSMOS_CONNECTION_STRING', secretRef: 'cosmos-connection-string' }
            { name: 'COSMOS_DATABASE_NAME', value: 'buildflow' }
            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAiDeployment }
            { name: 'AZURE_DALLE_DEPLOYMENT', value: 'gpt-image-1.5' }
            { name: 'AZURE_DALLE_IMAGE_SIZE', value: '1536x1024' }
            { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-connection' }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', secretRef: 'storage-account-name' }
            { name: 'AZURE_STORAGE_ACCOUNT_KEY', secretRef: 'storage-account-key' }
            { name: 'ACS_CONNECTION_STRING', secretRef: 'acs-connection-string' }
            { name: 'ACS_SENDER_ADDRESS', value: acsSenderAddress }
            { name: 'CORS_ORIGINS', value: corsOrigins }
          ], environment != 'prod' && !empty(devBypassEmail) ? [
            { name: 'DEV_BYPASS_EMAIL', value: devBypassEmail }
          ] : [], !empty(githubToken) ? [
            { name: 'GITHUB_TOKEN', secretRef: 'github-token' }
          ] : [], !empty(azureOpenAiKey) ? [
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'azure-openai-key' }
          ] : [], !empty(youtubeApiKey) ? [
            { name: 'YOUTUBE_API_KEY', secretRef: 'youtube-api-key' }
          ] : [], [
            { name: 'AZURE_SEARCH_ENDPOINT', value: search.outputs.searchEndpoint }
            { name: 'AZURE_SEARCH_API_KEY', secretRef: 'search-admin-key' }
            { name: 'AZURE_SEARCH_INDEX_NAME', value: 'buildflow-content' }
          ])
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8001
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8001
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: environment == 'prod' ? 1 : 1
        maxReplicas: environment == 'prod' ? 10 : 3
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

// Outputs
output apiUrl string = 'https://${apiContainerApp.properties.configuration.ingress.fqdn}'
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output keyVaultUri string = keyVault.properties.vaultUri
output managedIdentityId string = managedIdentity.id
output containerAppsEnvironmentId string = containerAppsEnv.id

// ============================================================================
// Azure AI Search Module (T103)
// ============================================================================

// T103: Azure AI Search Module
module search 'modules/search.bicep' = {
  name: 'searchDeployment'
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    managedIdentityPrincipalId: managedIdentity.properties.principalId
  }
}

// Store Search admin key in Key Vault
resource searchAdminKeyKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'search-admin-key'
  properties: {
    value: search.outputs.adminKey
  }
}

// ============================================================================
// Monitoring Module (T802)
// ============================================================================

module monitoring 'modules/monitoring.bicep' = if (enableMonitoring) {
  name: 'monitoringDeployment'
  params: {
    projectName: projectName
    environment: environment
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.id
    alertEmail: alertEmail
    enableDetailedAlerts: environment == 'prod'
  }
}

// Store App Insights connection string in Key Vault
resource appInsightsConnectionKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = if (enableMonitoring) {
  parent: keyVault
  name: 'appinsights-connection'
  properties: {
    value: monitoring!.outputs.appInsightsConnectionString
  }
}

// ============================================================================
// Storage & Search Outputs
// ============================================================================

output storageAccountName string = storage.outputs.storageAccountName
output storageBlobEndpoint string = storage.outputs.blobEndpoint
output searchServiceName string = search.outputs.searchServiceName
output searchEndpoint string = search.outputs.searchEndpoint

// Monitoring outputs
output appInsightsName string = enableMonitoring ? monitoring!.outputs.appInsightsName : ''
output appInsightsConnectionString string = enableMonitoring ? monitoring!.outputs.appInsightsConnectionString : ''

// ============================================================================
// Frontend Static Web App (T901)
// ============================================================================

module staticWebApp 'modules/static-web-app.bicep' = if (enableFrontend) {
  name: 'staticWebAppDeployment'
  params: {
    projectName: projectName
    environment: environment
    tags: tags
  }
}

// Store SWA deployment token in Key Vault
resource swaDeploymentTokenKv 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = if (enableFrontend) {
  parent: keyVault
  name: 'swa-deployment-token'
  properties: {
    value: staticWebApp!.outputs.deploymentToken
  }
}

// Frontend outputs
output staticWebAppName string = enableFrontend ? staticWebApp!.outputs.staticWebAppName : ''
output staticWebAppUrl string = enableFrontend ? staticWebApp!.outputs.staticWebAppUrl : ''

// Container Registry outputs
output containerRegistryName string = containerRegistry.outputs.registryName
output containerRegistryLoginServer string = containerRegistry.outputs.registryLoginServer
