// ============================================================================
// Azure AI Search Module - T103
// Search service for content discovery and semantic search
// ============================================================================

@description('Project name for resource naming')
param projectName string

@description('Environment name (dev, stg, prod)')
param environment string

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Resource tags')
param tags object = {}

@description('User Assigned Managed Identity principal ID for RBAC')
param managedIdentityPrincipalId string

// ============================================================================
// Variables
// ============================================================================

var uniqueSuffix = uniqueString(resourceGroup().id, projectName)
// Search service names: 2-60 chars, lowercase, numbers, dashes (no consecutive dashes)
var searchServiceName = toLower('srch-${projectName}-${environment}-${uniqueSuffix}')

// SKU based on environment - 'free' for dev, 'basic' or 'standard' for prod
var skuName = environment == 'prod' ? 'standard' : 'basic'

// Replica and partition counts
var replicaCount = environment == 'prod' ? 2 : 1
var partitionCount = 1

// ============================================================================
// Azure AI Search Service
// ============================================================================

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: 'default'
    publicNetworkAccess: 'enabled' // Dev environment
    networkRuleSet: {
      bypass: 'AzurePortal'
      ipRules: []
    }
    encryptionWithCmk: {
      enforcement: 'Unspecified'
    }
    disableLocalAuth: false
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    semanticSearch: environment == 'prod' ? 'standard' : 'free'
  }
}

// ============================================================================
// RBAC Assignments
// ============================================================================

// Search Index Data Contributor - allows indexing data
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

resource searchIndexDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, managedIdentityPrincipalId, searchIndexDataContributorRoleId)
  scope: searchService
  properties: {
    principalId: managedIdentityPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Reader - allows querying data
var searchIndexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

resource searchIndexDataReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, managedIdentityPrincipalId, searchIndexDataReaderRoleId)
  scope: searchService
  properties: {
    principalId: managedIdentityPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReaderRoleId)
    principalType: 'ServicePrincipal'
  }
}

// Search Service Contributor - for managing indexes
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

resource searchServiceContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, managedIdentityPrincipalId, searchServiceContributorRoleId)
  scope: searchService
  properties: {
    principalId: managedIdentityPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Search service name')
output searchServiceName string = searchService.name

@description('Search service ID')
output searchServiceId string = searchService.id

@description('Search service endpoint')
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'

@description('Search service system-assigned identity principal ID')
output searchServicePrincipalId string = searchService.identity.principalId

@description('Search admin key')
@secure()
output adminKey string = searchService.listAdminKeys().primaryKey

@description('Search query key')
@secure()
output queryKey string = searchService.listQueryKeys().value[0].key
