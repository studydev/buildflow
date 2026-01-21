// Azure Static Web Apps Module
// Per T901: Frontend deployment infrastructure

@description('Project name for resource naming')
param projectName string

@description('Environment name')
param environment string

@description('Azure region - Note: SWA only supports limited regions')
param location string

@description('Resource tags')
param tags object

@description('API backend URL for proxying')
param apiBackendUrl string = ''

// Variables
var swaName = 'swa-${projectName}-${environment}-${uniqueString(resourceGroup().id)}'
// SWA supported regions: westus2, centralus, eastus2, westeurope, eastasia
var swaLocation = 'eastasia'

// Static Web App resource
resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: swaName
  location: swaLocation
  tags: tags
  sku: {
    name: environment == 'prod' ? 'Standard' : 'Free'
    tier: environment == 'prod' ? 'Standard' : 'Free'
  }
  properties: {
    stagingEnvironmentPolicy: 'Enabled'
    allowConfigFileUpdates: true
    buildProperties: {
      skipGithubActionWorkflowGeneration: true
    }
  }
}

// Note: Backend API connection is handled via staticwebapp.config.json routing
// Container Apps backend doesn't support linkedBackends, use reverse proxy config instead

// Custom domain configuration placeholder
// Note: Custom domains should be configured after deployment

// Outputs
output staticWebAppName string = staticWebApp.name
output staticWebAppDefaultHostname string = staticWebApp.properties.defaultHostname
output staticWebAppUrl string = 'https://${staticWebApp.properties.defaultHostname}'

// Note: Deployment token should be retrieved from Key Vault after deployment
// az staticwebapp secrets list --name <swa-name> --query "properties.apiKey"
#disable-next-line outputs-should-not-contain-secrets
output deploymentToken string = staticWebApp.listSecrets().properties.apiKey
