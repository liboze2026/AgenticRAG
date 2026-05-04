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
]

const router = createRouter({ history: createWebHistory(), routes })
export default router
