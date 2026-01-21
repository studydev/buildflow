// ============================================================================
// Container Apps Jobs Module - T101
// Pipeline worker jobs with Service Bus triggers
// ============================================================================

@description('Project name for resource naming')
param projectName string

@description('Environment name (dev, stg, prod)')
param environment string

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Resource tags')
param tags object = {}

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('User Assigned Managed Identity ID')
param managedIdentityId string

@description('Container Registry login server')
param containerRegistryLoginServer string

@description('Container image tag')
param imageTag string = 'latest'

@description('Service Bus namespace name')
param serviceBusName string

@description('Service Bus connection string (for KEDA scaler)')
@secure()
param serviceBusConnectionString string

// ============================================================================
// Variables
// ============================================================================

// Pipeline job configurations
var pipelineJobs = [
  {
    name: 'analysis'
    subscriptionName: 'analysis-sub'
    displayName: 'GitHub Analysis Pipeline'
    cpu: '0.5'
    memory: '1Gi'
  }
  {
    name: 'enrichment'
    subscriptionName: 'enrichment-sub'
    displayName: 'Content Enrichment Pipeline'
    cpu: '1.0'
    memory: '2Gi'
  }
  {
    name: 'localization'
    subscriptionName: 'localization-sub'
    displayName: 'Localization Pipeline'
    cpu: '1.0'
    memory: '2Gi'
  }
  {
    name: 'asset-generation'
    subscriptionName: 'asset-generation-sub'
    displayName: 'Asset Generation Pipeline'
    cpu: '1.0'
    memory: '2Gi'
  }
  {
    name: 'indexing'
    subscriptionName: 'indexing-sub'
    displayName: 'Search Indexing Pipeline'
    cpu: '0.5'
    memory: '1Gi'
  }
]

var topicName = 'pipeline-triggers'

// ============================================================================
// Container Apps Jobs - Event Triggered by Service Bus
// ============================================================================

resource containerAppsJobs 'Microsoft.App/jobs@2024-03-01' = [for job in pipelineJobs: {
  name: 'caj-${job.name}-${projectName}-${environment}'
  location: location
  tags: union(tags, {
    pipelineType: job.name
    component: 'pipeline-worker'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    workloadProfileName: 'Consumption'
    
    configuration: {
      triggerType: 'Event'
      replicaTimeout: 1800 // 30 minutes max execution time
      replicaRetryLimit: 2
      
      // Event trigger configuration with Service Bus
      eventTriggerConfig: {
        replicaCompletionCount: 1
        parallelism: 1
        scale: {
          minExecutions: 0
          maxExecutions: environment == 'prod' ? 10 : 3
          pollingInterval: 30
          rules: [
            {
              name: 'servicebus-trigger'
              type: 'azure-servicebus'
              metadata: {
                topicName: topicName
                subscriptionName: job.subscriptionName
                namespace: serviceBusName
                messageCount: '1'
              }
              auth: [
                {
                  secretRef: 'servicebus-connection'
                  triggerParameter: 'connection'
                }
              ]
            }
          ]
        }
      }
      
      // Secrets
      secrets: [
        {
          name: 'servicebus-connection'
          value: serviceBusConnectionString
        }
      ]
      
      // Container Registry (using managed identity)
      registries: [
        {
          server: containerRegistryLoginServer
          identity: managedIdentityId
        }
      ]
    }
    
    template: {
      containers: [
        {
          name: 'pipeline-worker'
          image: '${containerRegistryLoginServer}/buildflow-pipeline:${imageTag}'
          resources: {
            cpu: json(job.cpu)
            memory: job.memory
          }
          env: [
            {
              name: 'PIPELINE_TYPE'
              value: job.name
            }
            {
              name: 'ENVIRONMENT'
              value: environment
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: '' // Will be set from managed identity
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: '${serviceBusName}.servicebus.windows.net'
            }
            {
              name: 'SERVICE_BUS_TOPIC_NAME'
              value: topicName
            }
            {
              name: 'SERVICE_BUS_SUBSCRIPTION_NAME'
              value: job.subscriptionName
            }
            // Connection string from secret for pipeline code
            {
              name: 'SERVICE_BUS_CONNECTION_STRING'
              secretRef: 'servicebus-connection'
            }
          ]
        }
      ]
    }
  }
}]

// ============================================================================
// Outputs
// ============================================================================

@description('Container Apps Jobs names')
output jobNames array = [for (job, i) in pipelineJobs: containerAppsJobs[i].name]

@description('Container Apps Jobs resource IDs')
output jobIds array = [for (job, i) in pipelineJobs: containerAppsJobs[i].id]

@description('Pipeline job configuration')
output pipelineJobConfig array = pipelineJobs
