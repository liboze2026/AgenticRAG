import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api', timeout: 120000 })

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail || error.message || '未知错误'
    const status = error.response?.status
    ElMessage.error(status ? `[${status}] ${detail}` : detail)
    return Promise.reject(error)
  }
)

// ---------------------------------------------------------------------------
// Layout / Provenance types
// ---------------------------------------------------------------------------

export interface BoundingBox {
  x0: number; y0: number; x1: number; y1: number
}

export interface LayoutElement {
  element_type: string       // "text_block" | "table" | "figure" | "heading"
  bbox: BoundingBox
  text?: string
  image_path?: string
  confidence: number
}

export interface PageLayout {
  document_id: string
  page_number: number
  page_width: number
  page_height: number
  elements: LayoutElement[]
}

// ---------------------------------------------------------------------------
// Core retrieval / query types
// ---------------------------------------------------------------------------

export interface RetrievalResult {
  document_id: string
  page_number: number
  score: number
  image_path: string
  layout?: PageLayout
}

export interface QueryResponse {
  answer: string
  sources: RetrievalResult[]
  timing?: Record<string, number>
}

// ---------------------------------------------------------------------------
// Chat / Session types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources: RetrievalResult[]
  timestamp: string
}

export interface ChatSession {
  session_id: string
  document_ids: string[]
  messages: ChatMessage[]
  created_at: string
  updated_at: string
}

export interface ChatResponse {
  message: { role: string; content: string }
  sources: RetrievalResult[]
  session_id: string
  timing: Record<string, number>
}

// ---------------------------------------------------------------------------
// Document / Dataset / Experiment types
// ---------------------------------------------------------------------------

export interface DocumentInfo {
  id: string
  filename: string
  total_pages: number
  status: string
  indexed_pages: number
  dataset_id: number | null
}

export interface DatasetInfo {
  id: number
  name: string
  description: string
  created_at: string
  document_count: number
}

export interface PerQueryResult {
  query: string
  relevant: string[]
  retrieved: string[]
  rr: number
  recall_at_k: Record<number, number>
  timing_ms: Record<string, number>
}

export interface ExperimentRecord {
  id: number
  created_at: string
  pipeline_config: { yaml?: Record<string, any>; effective?: Record<string, any> }
  metrics: {
    recall_at_k: Record<number, number>
    mrr: number
    total_queries: number
    avg_timing_ms?: Record<string, number>
    per_query?: PerQueryResult[]
  }
  total_queries: number
  note: string
  dataset_id: number | null
}

export interface CacheStats {
  enabled: boolean
  entries: number
  size_bytes: number
}

export interface EvalMetrics {
  recall_at_k: Record<number, number>
  mrr: number
  total_queries: number
  avg_timing_ms?: Record<string, number>
}

export interface PipelineInfo {
  available: Record<string, string[]>; current: Record<string, string | null>
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export const documentsApi = {
  upload: (file: File, datasetId?: number) => {
    const form = new FormData()
    form.append('file', file)
    const params = datasetId !== undefined ? { dataset_id: datasetId } : {}
    return api.post<DocumentInfo>('/documents/upload', form, { params })
  },
  list: (datasetId?: number) => {
    const params = datasetId !== undefined ? { dataset_id: datasetId } : {}
    return api.get<DocumentInfo[]>('/documents', { params })
  },
  status: (id: string) => api.get<DocumentInfo>(`/documents/${id}/status`),
  delete: (id: string) => api.delete(`/documents/${id}`),
  retry: (id: string) => api.post(`/documents/${id}/retry`),
  layout: (id: string, page: number) => api.get<PageLayout>(`/documents/${id}/layout/${page}`),
}

export const datasetsApi = {
  list: () => api.get<DatasetInfo[]>('/datasets'),
  create: (name: string, description = '') => api.post<DatasetInfo>('/datasets', { name, description }),
  delete: (id: number) => api.delete(`/datasets/${id}`),
}

export const queryApi = {
  query: (query: string, topK = 5) => api.post<QueryResponse>('/query', { query, top_k: topK }),
  retrieve: (query: string, topK = 5) => api.post<{ results: RetrievalResult[]; timing?: Record<string, number> }>('/retrieve', { query, top_k: topK }),
}

export const chatApi = {
  send: (messages: Array<{ role: string; content: string }>, documentIds: string[] = [], sessionId?: string, topK = 5) =>
    api.post<ChatResponse>('/chat', {
      messages,
      document_ids: documentIds,
      session_id: sessionId,
      top_k: topK,
    }),
  listSessions: () => api.get<ChatSession[]>('/chat/sessions'),
  getSession: (id: string) => api.get<ChatSession>(`/chat/sessions/${id}`),
  deleteSession: (id: string) => api.delete(`/chat/sessions/${id}`),
}

export const experimentsApi = {
  getPipelines: () => api.get<PipelineInfo>('/pipelines'),
  switchPipeline: (config: Record<string, string | null>) => api.put('/pipelines/active', config),
  evaluate: (queries: Array<{ query: string; relevant: string[] }>, topK = 10, note = '', datasetId?: number) =>
    api.post<EvalMetrics & { experiment_id: number; avg_timing_ms?: Record<string, number> }>(
      '/experiments/evaluate',
      { queries, top_k: topK, note, dataset_id: datasetId }
    ),
  listHistory: (limit = 100) => api.get<ExperimentRecord[]>('/experiments/history', { params: { limit } }),
  getHistory: (id: number) => api.get<ExperimentRecord>(`/experiments/${id}`),
  deleteHistory: (id: number) => api.delete(`/experiments/${id}`),
  generateHardNegatives: (evalData: Array<{ query: string; relevant: string[] }>, window = 2) =>
    api.post<{ eval_data: Array<{ query: string; relevant: string[]; hard_negatives: string[] }> }>(
      '/experiments/hard_negatives',
      { eval_data: evalData, window }
    ),
}

export const cacheApi = {
  stats: () => api.get<{ query_cache: CacheStats; generation_cache: CacheStats }>('/cache/stats'),
  clearQuery: () => api.delete('/cache/query'),
  clearGeneration: () => api.delete('/cache/generation'),
}

export const systemApi = {
  health: () => api.get('/health'),
}

export default api
