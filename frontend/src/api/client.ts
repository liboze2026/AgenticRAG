import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 120000 })

export interface DocumentInfo {
  id: string; filename: string; total_pages: number; status: string; indexed_pages: number
}

export interface RetrievalResult {
  document_id: string; page_number: number; score: number; image_path: string
}

export interface QueryResponse {
  answer: string; sources: RetrievalResult[]
}

export interface EvalMetrics {
  recall_at_k: Record<number, number>; mrr: number; total_queries: number
}

export interface PipelineInfo {
  available: Record<string, string[]>; current: Record<string, string | null>
}

export const documentsApi = {
  upload: (file: File) => { const form = new FormData(); form.append('file', file); return api.post<DocumentInfo>('/documents/upload', form) },
  list: () => api.get<DocumentInfo[]>('/documents'),
  status: (id: string) => api.get<DocumentInfo>(`/documents/${id}/status`),
  delete: (id: string) => api.delete(`/documents/${id}`),
}

export const queryApi = {
  query: (query: string, topK = 5) => api.post<QueryResponse>('/query', { query, top_k: topK }),
  retrieve: (query: string, topK = 5) => api.post<{ results: RetrievalResult[] }>('/retrieve', { query, top_k: topK }),
}

export const experimentsApi = {
  getPipelines: () => api.get<PipelineInfo>('/pipelines'),
  switchPipeline: (config: Record<string, string | null>) => api.put('/pipelines/active', config),
  evaluate: (queries: Array<{ query: string; relevant: string[] }>, topK = 10) => api.post<EvalMetrics>('/experiments/evaluate', { queries, top_k: topK }),
}

export const systemApi = {
  health: () => api.get('/health'),
}

export default api
