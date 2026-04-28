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
]

const router = createRouter({ history: createWebHistory(), routes })
export default router
