// ============================================================================
// Azure Function App Module – Daily Metadata Refresh
// ============================================================================
// Runs a Python timer function at KST 02:00 daily to refresh
// GitHub (stars, forks) and YouTube (views, likes) metadata.

@description('Project name')
param projectName string

@description('Environment name')
param environment string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Log Analytics Workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Cosmos DB connection string')
@secure()
param cosmosConnectionString string

@description('GitHub Personal Access Token')
@secure()
param githubToken string = ''

@description('YouTube Data API v3 key')
@secure()
param youtubeApiKey string = ''

@description('Azure AI Search endpoint')
param searchEndpoint string = ''

@description('Azure AI Search admin key')
@secure()
param searchAdminKey string = ''

@description('Application Insights connection string')
param appInsightsConnectionString string = ''

// ─── Variables ──────────────────────────────────────────────────────────────

var shortSuffix = take(uniqueString(resourceGroup().id), 6)
// Storage account name: 3-24 lowercase alphanumeric only
var funcStorageName = toLower(take('stfunc${projectName}${environment}${shortSuffix}', 24))
var functionAppName = 'func-${projectName}-${environment}-${shortSuffix}'
var appServicePlanName = 'asp-${projectName}-func-${environment}-${shortSuffix}'

// ─── Storage Account (AzureWebJobsStorage) ──────────────────────────────────

resource funcStorage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: funcStorageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

// ─── App Service Plan (Consumption / Y1) ────────────────────────────────────

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  kind: 'functionapp'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // Required for Linux
  }
}

// ─── Function App ───────────────────────────────────────────────────────────

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  tags: union(tags, { 'azd-service-name': 'functions' })
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${funcStorage.name};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${funcStorage.listKeys().keys[0].value}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        // ── Application Settings ──
        {
          name: 'COSMOS_CONNECTION_STRING'
          value: cosmosConnectionString
        }
        {
          name: 'COSMOS_DATABASE_NAME'
          value: 'buildflow'
        }
        {
          name: 'GITHUB_TOKEN'
          value: githubToken
        }
        {
          name: 'YOUTUBE_API_KEY'
          value: youtubeApiKey
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: searchEndpoint
        }
        {
          name: 'AZURE_SEARCH_API_KEY'
          value: searchAdminKey
        }
        // ── Monitoring ──
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
      ]
    }
  }
}

// ─── Outputs ────────────────────────────────────────────────────────────────

// ─── Diagnostic Settings ────────────────────────────────────────────────────

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${functionApp.name}-diagnostics'
  scope: functionApp
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'FunctionAppLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// ─── Outputs (final) ────────────────────────────────────────────────────────

output functionAppName string = functionApp.name
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output functionStorageName string = funcStorage.name
