// BuildFlow Infrastructure - Monitoring Module
// Per tasks.md T802: Setup monitoring and alerting
// 
// Resources:
// - Application Insights for API telemetry
// - Log Analytics Workspace (shared with Container Apps)
// - Alert rules for failures

targetScope = 'resourceGroup'

// Parameters
@description('Project name for resource naming')
param projectName string

@description('Environment name (dev, staging, prod)')
param environment string

@description('Azure region')
param location string

@description('Tags for resources')
param tags object

@description('Log Analytics Workspace ID (existing)')
param logAnalyticsWorkspaceId string

@description('Container App name to monitor')
param containerAppName string = ''

@description('Action Group email for alerts')
param alertEmail string = ''

@description('Enable detailed alerts (prod only recommended)')
param enableDetailedAlerts bool = false

// Variables
var resourceSuffix = '${projectName}-${environment}'

// Reference existing Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${resourceSuffix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: environment == 'prod' ? 90 : 30
  }
}

// Action Group for Alerts
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (!empty(alertEmail)) {
  name: 'ag-${resourceSuffix}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: take('${projectName}${environment}', 12)
    enabled: true
    emailReceivers: [
      {
        name: 'Admin Email'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

// ============================================================================
// Alert Rules
// ============================================================================

// Alert: API Response Time > 5 seconds
resource responseTimeAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableDetailedAlerts) {
  name: 'alert-response-time-${resourceSuffix}'
  location: 'global'
  tags: tags
  properties: {
    description: 'API response time exceeds 5 seconds'
    severity: 2
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ResponseTime'
          metricName: 'requests/duration'
          operator: 'GreaterThan'
          threshold: 5000
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: !empty(alertEmail) ? [
      {
        actionGroupId: actionGroup.id
      }
    ] : []
  }
}

// Alert: High Error Rate (>5%)
resource errorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableDetailedAlerts) {
  name: 'alert-error-rate-${resourceSuffix}'
  location: 'global'
  tags: tags
  properties: {
    description: 'API error rate exceeds 5%'
    severity: 1
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'FailedRequests'
          metricName: 'requests/failed'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Count'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: !empty(alertEmail) ? [
      {
        actionGroupId: actionGroup.id
      }
    ] : []
  }
}

// Alert: Service Availability < 99%
resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableDetailedAlerts && environment == 'prod') {
  name: 'alert-availability-${resourceSuffix}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Service availability below 99%'
    severity: 0
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT1H'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Availability'
          metricName: 'availabilityResults/availabilityPercentage'
          operator: 'LessThan'
          threshold: 99
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: !empty(alertEmail) ? [
      {
        actionGroupId: actionGroup.id
      }
    ] : []
  }
}

// ============================================================================
// Log Analytics Queries (Saved Searches)
// ============================================================================

// Saved Query: Pipeline Failures
resource pipelineFailuresQuery 'Microsoft.OperationalInsights/workspaces/savedSearches@2020-08-01' = {
  name: 'pipeline-failures-${resourceSuffix}'
  parent: logAnalyticsWorkspace
  properties: {
    category: 'BuildFlow'
    displayName: 'Pipeline Failures (Last 24h)'
    query: '''
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(24h)
      | where Log_s contains "error" or Log_s contains "failed" or Log_s contains "exception"
      | project TimeGenerated, ContainerAppName_s, Log_s
      | order by TimeGenerated desc
    '''
    version: 2
  }
}

// Saved Query: API Request Summary
resource apiRequestsQuery 'Microsoft.OperationalInsights/workspaces/savedSearches@2020-08-01' = {
  name: 'api-requests-${resourceSuffix}'
  parent: logAnalyticsWorkspace
  properties: {
    category: 'BuildFlow'
    displayName: 'API Requests Summary (Last 1h)'
    query: '''
      requests
      | where timestamp > ago(1h)
      | summarize 
          TotalRequests = count(),
          FailedRequests = countif(success == false),
          AvgDuration = avg(duration),
          P95Duration = percentile(duration, 95)
        by bin(timestamp, 5m)
      | order by timestamp desc
    '''
    version: 2
  }
}

// Saved Query: Container App Job Executions
resource jobExecutionsQuery 'Microsoft.OperationalInsights/workspaces/savedSearches@2020-08-01' = {
  name: 'job-executions-${resourceSuffix}'
  parent: logAnalyticsWorkspace
  properties: {
    category: 'BuildFlow'
    displayName: 'Container App Job Executions'
    query: '''
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(24h)
      | where ContainerAppName_s contains "caj-"
      | summarize 
          LogCount = count(),
          Errors = countif(Log_s contains "error" or Log_s contains "failed")
        by ContainerAppName_s, bin(TimeGenerated, 1h)
      | order by TimeGenerated desc
    '''
    version: 2
  }
}

// ============================================================================
// Workbooks
// ============================================================================

// Dashboard Workbook for BuildFlow
resource dashboardWorkbook 'Microsoft.Insights/workbooks@2022-04-01' = {
  name: guid(resourceGroup().id, 'buildflow-dashboard')
  location: location
  tags: union(tags, { 'hidden-title': 'BuildFlow Operations Dashboard' })
  kind: 'shared'
  properties: {
    displayName: 'BuildFlow Operations Dashboard'
    category: 'workbook'
    version: '1.0'
    serializedData: '''
{
  "version": "Notebook/1.0",
  "items": [
    {
      "type": 1,
      "content": {
        "json": "# BuildFlow Operations Dashboard\n\nReal-time monitoring for API and Pipeline operations."
      }
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "query": "requests | where timestamp > ago(1h) | summarize count() by bin(timestamp, 5m)",
        "size": 0,
        "title": "API Requests (Last Hour)",
        "queryType": 0,
        "resourceType": "microsoft.insights/components",
        "visualization": "timechart"
      }
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "query": "requests | where timestamp > ago(1h) | summarize count() by resultCode",
        "size": 0,
        "title": "Response Codes Distribution",
        "queryType": 0,
        "resourceType": "microsoft.insights/components",
        "visualization": "piechart"
      }
    }
  ]
}
'''
    sourceId: appInsights.id
  }
}

// ============================================================================
// Outputs
// ============================================================================

output appInsightsId string = appInsights.id
output appInsightsName string = appInsights.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
output actionGroupId string = !empty(alertEmail) ? actionGroup.id : ''
