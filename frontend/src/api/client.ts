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

export interface RetrievalResult {
  document_id: string; page_number: number; score: number; image_path: string
}

export interface QueryResponse {
  answer: string
  sources: RetrievalResult[]
  timing?: Record<string, number>
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
}

export const datasetsApi = {
  list: () => api.get<DatasetInfo[]>('/datasets'),
  create: (name: string, description = '') => api.post<DatasetInfo>('/datasets', { name, description }),
  delete: (id: number) => api.delete(`/datasets/${id}`),
}

export const queryApi = {
  query: (query: string, topK = 5) => api.post<QueryResponse>('/query', { query, top_k: topK }),
  retrieve: (query: string, topK = 5) => api.post<{ results: RetrievalResult[] }>('/retrieve', { query, top_k: topK }),
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
