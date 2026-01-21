// ============================================================================
// Service Bus Module - T100
// Azure Service Bus for pipeline message queue
// ============================================================================

@description('Project name for resource naming')
param projectName string

@description('Environment name (dev, stg, prod)')
param environment string

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Resource tags')
param tags object = {}

// ============================================================================
// Variables
// ============================================================================

var uniqueSuffix = uniqueString(resourceGroup().id, projectName)
var serviceBusName = 'sb-${projectName}-${environment}-${uniqueSuffix}'

// SKU configuration - Standard for Dev (cost-effective), Premium for Prod
var skuName = environment == 'prod' ? 'Premium' : 'Standard'

// Topic names
var pipelineTriggersTopicName = 'pipeline-triggers'
var pipelineEventsTopicName = 'pipeline-events'

// Subscription names for each pipeline type
var subscriptionNames = [
  'analysis-sub'
  'enrichment-sub'
  'localization-sub'
  'asset-generation-sub'
  'indexing-sub'
]

// ============================================================================
// Service Bus Namespace
// ============================================================================

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: serviceBusName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuName
    capacity: skuName == 'Premium' ? 1 : 0
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    zoneRedundant: environment == 'prod'
  }
}

// ============================================================================
// Topics
// ============================================================================

// Pipeline Triggers Topic - receives pipeline execution requests
resource pipelineTriggersQueue 'Microsoft.ServiceBus/namespaces/topics@2024-01-01' = {
  parent: serviceBusNamespace
  name: pipelineTriggersTopicName
  properties: {
    maxSizeInMegabytes: 1024
    defaultMessageTimeToLive: 'P1D' // 1 day
    enableBatchedOperations: true
    supportOrdering: true
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'PT10M' // 10 minutes
  }
}

// Pipeline Events Topic - publishes pipeline status updates
resource pipelineEventsQueue 'Microsoft.ServiceBus/namespaces/topics@2024-01-01' = {
  parent: serviceBusNamespace
  name: pipelineEventsTopicName
  properties: {
    maxSizeInMegabytes: 1024
    defaultMessageTimeToLive: 'P1D'
    enableBatchedOperations: true
    supportOrdering: false
  }
}

// ============================================================================
// Subscriptions for Pipeline Triggers
// Each pipeline type subscribes to its specific messages
// ============================================================================

resource analysisSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: pipelineTriggersQueue
  name: 'analysis-sub'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M' // 5 minutes lock
    deadLetteringOnMessageExpiration: true
    deadLetteringOnFilterEvaluationExceptions: true
  }
}

resource analysisFilterRule 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2024-01-01' = {
  parent: analysisSubscription
  name: 'PipelineTypeFilter'
  properties: {
    filterType: 'CorrelationFilter'
    correlationFilter: {
      properties: {
        pipelineType: 'analysis'
      }
    }
    action: {}
  }
}

resource enrichmentSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: pipelineTriggersQueue
  name: 'enrichment-sub'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M'
    deadLetteringOnMessageExpiration: true
    deadLetteringOnFilterEvaluationExceptions: true
  }
}

resource enrichmentFilterRule 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2024-01-01' = {
  parent: enrichmentSubscription
  name: 'PipelineTypeFilter'
  properties: {
    filterType: 'CorrelationFilter'
    correlationFilter: {
      properties: {
        pipelineType: 'enrichment'
      }
    }
    action: {}
  }
}

resource localizationSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: pipelineTriggersQueue
  name: 'localization-sub'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M'
    deadLetteringOnMessageExpiration: true
    deadLetteringOnFilterEvaluationExceptions: true
  }
}

resource localizationFilterRule 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2024-01-01' = {
  parent: localizationSubscription
  name: 'PipelineTypeFilter'
  properties: {
    filterType: 'CorrelationFilter'
    correlationFilter: {
      properties: {
        pipelineType: 'localization'
      }
    }
    action: {}
  }
}

resource assetGenerationSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: pipelineTriggersQueue
  name: 'asset-generation-sub'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M'
    deadLetteringOnMessageExpiration: true
    deadLetteringOnFilterEvaluationExceptions: true
  }
}

resource assetGenerationFilterRule 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2024-01-01' = {
  parent: assetGenerationSubscription
  name: 'PipelineTypeFilter'
  properties: {
    filterType: 'CorrelationFilter'
    correlationFilter: {
      properties: {
        pipelineType: 'asset_generation'
      }
    }
    action: {}
  }
}

resource indexingSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: pipelineTriggersQueue
  name: 'indexing-sub'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M'
    deadLetteringOnMessageExpiration: true
    deadLetteringOnFilterEvaluationExceptions: true
  }
}

resource indexingFilterRule 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2024-01-01' = {
  parent: indexingSubscription
  name: 'PipelineTypeFilter'
  properties: {
    filterType: 'CorrelationFilter'
    correlationFilter: {
      properties: {
        pipelineType: 'indexing'
      }
    }
    action: {}
  }
}

// ============================================================================
// Subscription for Pipeline Events (monitoring/logging)
// ============================================================================

resource eventsMonitoringSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: pipelineEventsQueue
  name: 'monitoring-sub'
  properties: {
    maxDeliveryCount: 5
    lockDuration: 'PT1M'
    deadLetteringOnMessageExpiration: false
  }
}

// ============================================================================
// Authorization Rules
// ============================================================================

// Shared Access Policy for Pipeline Workers
resource pipelineWorkerAuthRule 'Microsoft.ServiceBus/namespaces/authorizationRules@2024-01-01' = {
  parent: serviceBusNamespace
  name: 'PipelineWorkerPolicy'
  properties: {
    rights: [
      'Listen'
      'Send'
    ]
  }
}

// Shared Access Policy for API (send only)
resource apiAuthRule 'Microsoft.ServiceBus/namespaces/authorizationRules@2024-01-01' = {
  parent: serviceBusNamespace
  name: 'ApiSendPolicy'
  properties: {
    rights: [
      'Send'
    ]
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Service Bus namespace name')
output serviceBusName string = serviceBusNamespace.name

@description('Service Bus namespace ID')
output serviceBusId string = serviceBusNamespace.id

@description('Service Bus endpoint')
output serviceBusEndpoint string = serviceBusNamespace.properties.serviceBusEndpoint

@description('Pipeline triggers topic name')
output pipelineTriggersTopicName string = pipelineTriggersQueue.name

@description('Pipeline events topic name')
output pipelineEventsTopicName string = pipelineEventsQueue.name

@description('Pipeline worker connection string')
@secure()
output pipelineWorkerConnectionString string = pipelineWorkerAuthRule.listKeys().primaryConnectionString

@description('API send-only connection string')
@secure()
output apiSendConnectionString string = apiAuthRule.listKeys().primaryConnectionString

@description('Subscription names for Container Apps Jobs triggers')
output subscriptionNames array = subscriptionNames
