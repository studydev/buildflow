// Azure Container Registry Module
// Container registry for API and Pipeline images

@description('Project name for resource naming')
param projectName string

@description('Environment name')
param environment string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Managed Identity Principal ID for AcrPull role')
param managedIdentityPrincipalId string

// Variables
var acrName = replace('cr${projectName}${environment}${uniqueString(resourceGroup().id)}', '-', '')

// Azure Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: take(acrName, 50)
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'Standard' : 'Basic'
  }
  properties: {
    adminUserEnabled: true
    publicNetworkAccess: 'Enabled'
    policies: {
      retentionPolicy: {
        days: environment == 'prod' ? 30 : 7
        status: 'enabled'
      }
    }
  }
}

// AcrPull role assignment for Managed Identity
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, managedIdentityPrincipalId, 'AcrPull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output registryName string = containerRegistry.name
output registryLoginServer string = containerRegistry.properties.loginServer
output registryId string = containerRegistry.id
