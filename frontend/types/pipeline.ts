/**
 * Pipeline Types for Frontend
 * 
 * Per tasks.md T205: Update analysis store for pipeline model.
 * Matches backend PipelineRun and PipelineMessage schemas.
 */

/**
 * Pipeline type constants
 * Matches backend app.models.enums.PipelineType
 */
export const PipelineType = {
  ANALYSIS: 'analysis',
  ENRICHMENT: 'enrichment',
  LOCALIZATION: 'localization',
  ASSET_GENERATION: 'asset_generation',
  INDEXING: 'indexing',
} as const

export type PipelineType = typeof PipelineType[keyof typeof PipelineType]

/**
 * Pipeline status constants
 * Matches backend app.models.enums.PipelineStatus
 */
export const PipelineStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
  RETRYING: 'retrying',
} as const

export type PipelineStatus = typeof PipelineStatus[keyof typeof PipelineStatus]

/**
 * Pipeline run from API response
 * Matches backend app.models.pipeline_run.PipelineRun
 */
export interface PipelineRun {
  id: string
  pipeline_type: PipelineType
  status: PipelineStatus
  enrichment_version: string
  input_params: Record<string, unknown>
  output_summary: Record<string, unknown> | null
  error_details: ErrorDetails | null
  content_id: string | null
  triggered_by: string | null
  parent_run_id: string | null
  job_id: string | null
  attempt_number: number
  correlation_id: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  // Additional fields for UI
  retry_count?: number
  max_retries?: number
  error_message?: string
  idempotency_key?: string
  raw_extraction_id?: string
}

/**
 * Error details structure
 */
export interface ErrorDetails {
  error_type: string
  error_message: string
  attempt_number: number
  timestamp: string
}

/**
 * Request to enqueue a new pipeline
 * Matches backend app.schemas.pipeline.EnqueuePipelineRequest
 */
export interface EnqueuePipelineRequest {
  pipeline_type: PipelineType | 'analysis'
  source_url?: string
  content_id?: string
  chain?: string
  enrichment_version?: string
  force_refresh?: boolean
}

/**
 * Response from enqueue API
 */
export interface EnqueuePipelineResponse {
  run_id: string
  status: PipelineStatus
  message?: string
}

/**
 * Pipeline history item (for content pipeline history)
 */
export interface PipelineHistoryItem {
  id: string
  pipeline_type: PipelineType
  status: PipelineStatus
  created_at: string
  completed_at: string | null
  duration_seconds: number | null
  attempt_number: number
  error_message: string | null
}

/**
 * Pipeline history response
 */
export interface PipelineHistoryResponse {
  items: PipelineHistoryItem[]
  total: number
  content_id: string
}

/**
 * Helper function to check if status is terminal
 */
export function isTerminalStatus(status: PipelineStatus): boolean {
  return (
    status === PipelineStatus.COMPLETED ||
    status === PipelineStatus.FAILED ||
    status === PipelineStatus.CANCELLED
  )
}

/**
 * Helper function to check if status is active (needs polling)
 */
export function isActiveStatus(status: PipelineStatus): boolean {
  return (
    status === PipelineStatus.PENDING ||
    status === PipelineStatus.RUNNING ||
    status === PipelineStatus.RETRYING
  )
}

/**
 * Get human-readable status text
 */
export function getStatusText(status: PipelineStatus): string {
  const statusTextMap: Record<PipelineStatus, string> = {
    [PipelineStatus.PENDING]: '대기 중',
    [PipelineStatus.RUNNING]: '실행 중',
    [PipelineStatus.COMPLETED]: '완료',
    [PipelineStatus.FAILED]: '실패',
    [PipelineStatus.CANCELLED]: '취소됨',
    [PipelineStatus.RETRYING]: '재시도 중',
  }
  return statusTextMap[status] || status
}

/**
 * Get status color class for UI
 */
export function getStatusColorClass(status: PipelineStatus): string {
  const colorMap: Record<PipelineStatus, string> = {
    [PipelineStatus.PENDING]: 'text-yellow-500',
    [PipelineStatus.RUNNING]: 'text-blue-500',
    [PipelineStatus.COMPLETED]: 'text-green-500',
    [PipelineStatus.FAILED]: 'text-red-500',
    [PipelineStatus.CANCELLED]: 'text-gray-500',
    [PipelineStatus.RETRYING]: 'text-orange-500',
  }
  return colorMap[status] || 'text-gray-500'
}

/**
 * Get pipeline type display name
 */
export function getPipelineTypeText(type: PipelineType): string {
  const typeTextMap: Record<PipelineType, string> = {
    [PipelineType.ANALYSIS]: '분석',
    [PipelineType.ENRICHMENT]: '보강',
    [PipelineType.LOCALIZATION]: '현지화',
    [PipelineType.ASSET_GENERATION]: '에셋 생성',
    [PipelineType.INDEXING]: '인덱싱',
  }
  return typeTextMap[type] || type
}
