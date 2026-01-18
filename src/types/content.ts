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