<template>
  <div style="height: 100vh; display: flex; flex-direction: column;">
    <el-container style="flex: 1; overflow: hidden;">
      <!-- Sidebar -->
      <el-aside width="220px" class="app-sidebar">
        <div class="app-logo">
          <svg class="app-logo__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          <div class="app-logo__text-block">
            <div class="app-logo__title">Agentic RAG</div>
            <div class="app-logo__subtitle">多模态文档检索系统</div>
          </div>
        </div>

        <div class="app-nav-group-label">主功能</div>
        <el-menu :default-active="route.path" router class="app-menu">
          <el-menu-item index="/">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
            <span>系统概览</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            <span>智能对话</span>
          </el-menu-item>
          <el-menu-item index="/query">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <span>检索问答</span>
          </el-menu-item>
        </el-menu>

        <div class="app-nav-group-label">管理</div>
        <el-menu :default-active="route.path" router class="app-menu">
          <el-menu-item index="/documents">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            <span>文档管理</span>
          </el-menu-item>
          <el-menu-item index="/datasets">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
            <span>数据集</span>
          </el-menu-item>
          <el-menu-item index="/experiments">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            <span>实验评测</span>
          </el-menu-item>
          <el-menu-item index="/system">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M8.46 8.46a5 5 0 0 0 0 7.07"/></svg>
            <span>系统状态</span>
          </el-menu-item>
        </el-menu>

        <div class="app-sidebar__version">v1.0 · 论文演示版</div>
      </el-aside>

      <!-- Main content -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<style scoped>
.app-sidebar {
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.app-logo {
  padding: 20px 16px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,.1);
  margin-bottom: 8px;
}
.app-logo__icon {
  width: 28px;
  height: 28px;
  color: #60a5fa;
  flex-shrink: 0;
}
.app-logo__title {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  line-height: 1.2;
}
.app-logo__subtitle {
  font-size: 11px;
  color: rgba(200,217,240,.7);
  line-height: 1.2;
  margin-top: 2px;
}

.app-nav-group-label {
  font-size: 10px;
  font-weight: 700;
  color: rgba(200,217,240,.5);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 8px 16px 2px;
}

.app-menu {
  border-right: none !important;
  background: transparent !important;
  flex-shrink: 0;
}

.nav-icon {
  width: 16px;
  height: 16px;
  margin-right: 10px;
  flex-shrink: 0;
  vertical-align: middle;
}

.app-sidebar__version {
  margin-top: auto;
  padding: 12px 16px;
  font-size: 11px;
  color: rgba(200,217,240,.4);
  border-top: 1px solid rgba(255,255,255,.08);
}

.app-main {
  background: var(--bg-base);
  overflow-y: auto;
  padding: 24px 28px;
}
</style>
