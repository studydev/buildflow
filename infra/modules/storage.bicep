// ============================================================================
// Storage Module - T102
// Azure Blob Storage for generated assets and raw extractions
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
// Storage account names must be 3-24 chars, lowercase alphanumeric only
var storageAccountName = toLower(take('st${projectName}${environment}${uniqueSuffix}', 24))

// SKU based on environment
var skuName = environment == 'prod' ? 'Standard_ZRS' : 'Standard_LRS'

// Container names
var containerNames = [
  'generated-assets'    // For cards, slides, summaries
  'raw-extractions'     // For GitHub API raw responses
  'pipeline-artifacts'  // For intermediate pipeline outputs
]

// ============================================================================
// Storage Account
// ============================================================================

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: skuName
  }
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true // Required for SDK access, consider disabling in prod
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow' // Dev environment allows public access
    }
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
      }
    }
  }
}

// ============================================================================
// Blob Service
// ============================================================================

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// ============================================================================
// Containers
// ============================================================================

resource generatedAssetsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: 'generated-assets'
  properties: {
    publicAccess: 'None'
    metadata: {
      purpose: 'Generated learning content assets (cards, slides, summaries)'
    }
  }
}

resource rawExtractionsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: 'raw-extractions'
  properties: {
    publicAccess: 'None'
    metadata: {
      purpose: 'Raw GitHub API extraction responses (immutable)'
    }
  }
}

resource pipelineArtifactsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: 'pipeline-artifacts'
  properties: {
    publicAccess: 'None'
    metadata: {
      purpose: 'Intermediate pipeline processing artifacts'
    }
  }
}

// ============================================================================
// RBAC - Storage Blob Data Contributor for Managed Identity
// ============================================================================

// Storage Blob Data Contributor role definition ID
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageBlobDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, managedIdentityPrincipalId, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    principalId: managedIdentityPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Lifecycle Management Policy
// ============================================================================

resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2024-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'MoveToCoolAfter30Days'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['pipeline-artifacts/']
            }
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: 30
                }
                delete: {
                  daysAfterModificationGreaterThan: 90
                }
              }
            }
          }
        }
        {
          name: 'ArchiveRawExtractions'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['raw-extractions/']
            }
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: 30
                }
                tierToArchive: {
                  daysAfterModificationGreaterThan: 90
                }
              }
            }
          }
        }
      ]
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Storage account name')
output storageAccountName string = storageAccount.name

@description('Storage account ID')
output storageAccountId string = storageAccount.id

@description('Primary blob endpoint')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

@description('Storage account primary access key')
@secure()
output primaryAccessKey string = storageAccount.listKeys().keys[0].value

@description('Connection string')
@secure()
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'

@description('Container names')
output containerNames array = containerNames
