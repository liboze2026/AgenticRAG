import axios from 'axios'
import type { AxiosError, AxiosRequestConfig } from 'axios'
import { msg } from '../design/message'

// 600s matches worker.timeout in config/default.yaml — first chat with VLM
// inference + base64 page images can exceed 120s, especially when the worker
// is cold-loading the model.
const api = axios.create({ baseURL: '/api', timeout: 600000 })

// Per-request flag set on the config object after a retry has been attempted.
// We retry once on transient failures (network error or 502/503/504), then
// surface the error to the caller exactly like before.
const RETRYABLE_STATUS = new Set([502, 503, 504])
const RETRY_DELAY_MS = 1000
// Endpoints that are silently polled at high frequency (e.g. health) should
// not trigger a user-visible toast on every transient failure — they would
// spam the screen and obscure real errors.
const SILENT_PATHS = ['/health']

function isRetryable(error: AxiosError): boolean {
  if (!error.response) return true                  // network / aborted / timeout
  return RETRYABLE_STATUS.has(error.response.status)
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined
    if (config && !config._retried && isRetryable(error)) {
      config._retried = true
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS))
      return api.request(config)
    }
    const path = config?.url || ''
    const silent = SILENT_PATHS.some((p) => path.includes(p))
    if (!silent) {
      const detail = (error.response?.data as any)?.detail || error.message || '未知错误'
      const status = error.response?.status
      msg.error(status ? `[${status}] ${detail}` : detail)
    }
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

// ---------------------------------------------------------------------------
// Lab feature types (Phase 1-5)
// ---------------------------------------------------------------------------

export interface ChannelResult {
  channel: 'bm25' | 'colpali' | 'rrf' | string
  results: RetrievalResult[]
  timing_ms: number
  note: string
}

export interface HybridCompareResponse {
  query: string
  channels: ChannelResult[]
  answer?: string | null
  fused_channel: string
}

export interface EvidenceRegion {
  document_id: string
  page_number: number
  bbox: BoundingBox
  label: string
  score: number
  quote: string
  citation: number
}

export interface VisaResponse {
  query: string
  answer: string
  sources: RetrievalResult[]
  evidence_regions: EvidenceRegion[]
  timing_ms: Record<string, number>
  note: string
}

export interface ScoreBucket { bin_start: number; bin_end: number; count: number }
export interface GmmComponent { mean: number; variance: number; weight: number }

export interface GmmResponse {
  query: string
  fixed_top_k: number
  dynamic_top_k: number
  cutoff_score: number
  histogram: ScoreBucket[]
  components: GmmComponent[]
  results: RetrievalResult[]
  note: string
  timing_ms: Record<string, number>
}

export interface RegionHit {
  document_id: string
  page_number: number
  element_index: number
  element_type: string
  bbox: BoundingBox
  score: number
  image_path: string
  text: string
}

export interface RegionResponse {
  query: string
  hits: RegionHit[]
  timing_ms: Record<string, number>
  note: string
}

export interface LabHealth {
  bm25_ready: boolean
  bm25_doc_count: number
  layout_ready: boolean
  sklearn_available: boolean
  region_collection_ready: boolean
  region_point_count: number
  main_pipeline_ok: boolean
  notes: string[]
}

export interface LabPhaseInfo {
  id: string; title: string; endpoint: string; method: string; desc: string
}
export interface LabInfo { phases: LabPhaseInfo[] }

export const labApi = {
  hybrid: (query: string, opts: { topK?: number; candidates?: number; rrfK?: number; doGenerate?: boolean } = {}) =>
    api.post<HybridCompareResponse>('/lab/hybrid', {
      query,
      top_k: opts.topK ?? 5,
      candidates: opts.candidates ?? 20,
      rrf_k: opts.rrfK ?? 60,
      do_generate: opts.doGenerate ?? false,
    }),
  visa: (query: string, topK = 5) =>
    api.post<VisaResponse>('/lab/visa', { query, top_k: topK }),
  gmm: (query: string, topK = 5, candidates = 20) =>
    api.post<GmmResponse>('/lab/gmm', { query, top_k: topK, candidates }),
  regionQuery: (query: string, topK = 8) =>
    api.post<RegionResponse>('/lab/region/query', { query, top_k: topK }),
  regionIndexOne: (docId: string, sync = false) =>
    api.post<{ state?: string; indexed?: number; skipped?: number; errors?: number; note: string; doc_id?: string }>(
      `/lab/region/index/${docId}`,
      undefined,
      { params: sync ? { sync: true } : {} },
    ),
  regionIndexAll: (sync = false) =>
    api.post<{ state?: string; indexed?: number; skipped?: number; errors?: number; documents?: number; note: string }>(
      `/lab/region/index_all`,
      undefined,
      { params: sync ? { sync: true } : {} },
    ),
  regionStatus: (docId: string) => api.get<{
    doc_id: string; state: string; indexed?: number; skipped?: number; errors?: number;
    current_page?: number; total_pages?: number; note?: string;
  }>(`/lab/region/status/${docId}`),
  regionJobs: () => api.get<Record<string, any>>(`/lab/region/jobs`),
  regionDelete: (docId: string) => api.delete(`/lab/region/${docId}`),
  health: () => api.get<LabHealth>('/lab/health'),
  info: () => api.get<LabInfo>('/lab/info'),
}

export default api
