import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/documents' },
  { path: '/documents', name: 'Documents', component: () => import('../views/DocumentsView.vue') },
  { path: '/query', name: 'Query', component: () => import('../views/QueryView.vue') },
  { path: '/experiments', name: 'Experiments', component: () => import('../views/ExperimentView.vue') },
  { path: '/system', name: 'System', component: () => import('../views/SystemView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })
export default router
