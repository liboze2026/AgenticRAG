import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue') },
  { path: '/chat', name: 'Chat', component: () => import('../views/ChatView.vue') },
  { path: '/query', name: 'Query', component: () => import('../views/QueryView.vue') },
  { path: '/documents', name: 'Documents', component: () => import('../views/DocumentsView.vue') },
  { path: '/datasets', name: 'Datasets', component: () => import('../views/DatasetsView.vue') },
  { path: '/experiments', name: 'Experiments', component: () => import('../views/ExperimentView.vue') },
  { path: '/visdom', name: 'VisDoM', component: () => import('../views/VisDomView.vue') },
  { path: '/system', name: 'System', component: () => import('../views/SystemView.vue') },
  // Lab — Phase 1-5
  { path: '/lab/hybrid',  name: 'LabHybrid', component: () => import('../views/lab/LabHybridView.vue') },
  { path: '/lab/visa',    name: 'LabVisa',   component: () => import('../views/lab/LabVisaView.vue') },
  { path: '/lab/gmm',     name: 'LabGmm',    component: () => import('../views/lab/LabGmmView.vue') },
  { path: '/lab/region',  name: 'LabRegion', component: () => import('../views/lab/LabRegionView.vue') },
  { path: '/lab/health',  name: 'LabHealth', component: () => import('../views/lab/LabHealthView.vue') },
  // Lab — Phase 6-9
  { path: '/lab/graph',     name: 'LabGraph',     component: () => import('../views/lab/LabGraphView.vue') },
  { path: '/lab/feedback',  name: 'LabFeedback',  component: () => import('../views/lab/LabFeedbackView.vue') },
  { path: '/lab/unified',   name: 'LabUnified',   component: () => import('../views/lab/LabUnifiedView.vue') },
  { path: '/lab/benchmark', name: 'LabBenchmark', component: () => import('../views/lab/LabBenchmarkView.vue') },
  // SOTA — Phase 0+
  { path: '/sota/datasets',    name: 'SotaDatasets',    component: () => import('../views/sota/SotaDatasetsView.vue') },
  { path: '/sota/methods',     name: 'SotaMethods',     component: () => import('../views/sota/SotaMethodsView.vue') },
  { path: '/sota/run',         name: 'SotaRunStudio',   component: () => import('../views/sota/SotaRunStudioView.vue') },
  { path: '/sota/leaderboard', name: 'SotaLeaderboard', component: () => import('../views/sota/SotaLeaderboardView.vue') },
  { path: '/sota/runs/:id',    name: 'SotaRunDetail',   component: () => import('../views/sota/SotaRunDetailView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })
export default router
