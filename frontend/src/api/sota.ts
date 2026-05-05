// SOTA experimentation client. All endpoints return HTTP 200 with envelope:
//   { ok: boolean, error_kind?: string, message?: string, ...data }
import api from './client'

export interface SotaEnvelope {
  ok: boolean
  error_kind?: string
  message?: string
  [k: string]: any
}

export const sotaApi = {
  health: () => api.get<SotaEnvelope>('/sota/health').then(r => r.data),
  datasets: () => api.get<SotaEnvelope>('/sota/datasets').then(r => r.data),
  checkDataset: (subset: string) =>
    api.post<SotaEnvelope>(`/sota/datasets/${subset}/check`).then(r => r.data),
  methods: () => api.get<SotaEnvelope>('/sota/methods').then(r => r.data),
  createRun: (body: {
    subsets: string[]
    methods: string[]
    top_k: number
    n_queries_per_subset?: number | null
    notes?: string
  }) => api.post<SotaEnvelope>('/sota/runs', body).then(r => r.data),
  listRuns: (limit = 50) =>
    api.get<SotaEnvelope>(`/sota/runs?limit=${limit}`).then(r => r.data),
  getRun: (id: string) => api.get<SotaEnvelope>(`/sota/runs/${id}`).then(r => r.data),
  cancelRun: (id: string) => api.post<SotaEnvelope>(`/sota/runs/${id}/cancel`).then(r => r.data),
  leaderboard: () => api.get<SotaEnvelope>('/sota/leaderboard').then(r => r.data),
}
