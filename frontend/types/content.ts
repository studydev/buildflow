export interface ContentItem {
  Topic: string
  Title: string
  Title_kr: string
  URL: string
  Categories: string
  Session_Description: string
  Session_Description_kr: string
  Learning_Objectives: string
  Lab_Modules: string
  Technologies_Used: string
  Prerequisites: string
  Contributor: string
  Reg_Date: string
  Requestor: string
  Update_Date: string
  Status: 'pending' | 'processing' | 'completed' | 'failed'
  PPTX_Link: string
  PDF_Link: string
  Demo_Link: string
  Youtube_Link: string
}

export interface RepoRequest {
  id: string
  repoUrl: string
  repoName: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  repoSummary: string
  regDate: string
  contributor: string
  requestor: string
}

// Analysis API 응답 타입
export interface AnalysisResult {
  title: string
  title_kr?: string
  description?: string
  description_kr?: string
  topic?: string
  content_type?: string
  categories: string[]
  level?: string
  duration_minutes?: number
  technologies: string[]
  prerequisites: string[]
  learning_objectives: string[]
  lab_modules: string[]
  raw_metadata?: Record<string, unknown>
}

export interface AnalysisRequest {
  id: string
  source_url: string
  status: 'pending' | 'fetching' | 'parsing' | 'completed' | 'failed'
  progress: number
  error_message?: string
  result?: AnalysisResult
  content_ids: string[]
  created_at: string
  updated_at: string
  completed_at?: string
}

// AnalysisResult를 ContentItem으로 변환하는 헬퍼
export function analysisResultToContentItem(
  analysis: AnalysisRequest,
  requestorEmail: string
): Partial<ContentItem> {
  const result = analysis.result
  if (!result) return {}
  
  return {
    Topic: result.topic || '',
    Title: result.title,
    Title_kr: result.title_kr || '',
    URL: analysis.source_url,
    Categories: result.categories.join(';'),
    Session_Description: result.description || '',
    Session_Description_kr: result.description_kr || '',
    Learning_Objectives: result.learning_objectives.join('; '),
    Lab_Modules: result.lab_modules.join('; '),
    Technologies_Used: result.technologies.join(';'),
    Prerequisites: result.prerequisites.join('; '),
    Requestor: requestorEmail,
    Reg_Date: analysis.created_at,
    Update_Date: analysis.updated_at,
    Status: analysis.status as ContentItem['Status'],
  }
}