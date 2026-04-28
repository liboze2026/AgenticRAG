<script setup lang="ts">
import { useRoute } from 'vue-router'
import Icon from '../design/Icons.vue'

const route = useRoute()

interface NavGroup {
  label: string
  items: { path: string; label: string; icon: string; chap: string }[]
}

const groups: NavGroup[] = [
  {
    label: '主功能',
    items: [
      { path: '/',         label: '系统概览', icon: 'home',     chap: '0' },
      { path: '/chat',     label: '多轮对话', icon: 'chat',     chap: '1' },
      { path: '/query',    label: '单次检索', icon: 'search',   chap: '2' },
    ],
  },
  {
    label: '数　据',
    items: [
      { path: '/documents',   label: '文档管理', icon: 'doc',      chap: '3' },
      { path: '/datasets',    label: '数据集',   icon: 'archive',  chap: '4' },
    ],
  },
  {
    label: '评　测',
    items: [
      { path: '/experiments', label: '实验评测', icon: 'flask',    chap: '5' },
      { path: '/visdom',      label: 'VisDoM 复现', icon: 'sparkles', chap: 'X' },
      { path: '/system',      label: '系统状态', icon: 'gauge',    chap: '6' },
    ],
  },
]
</script>

<template>
  <aside class="sb">
    <div class="sb__inner">
      <nav v-for="g in groups" :key="g.label" class="sb__group">
        <div class="sb__label">
          <span class="sb__label-mark"></span>
          <span class="sb__label-zh">{{ g.label }}</span>
          <span class="sb__label-line"></span>
        </div>
        <ul class="sb__list">
          <li v-for="item in g.items" :key="item.path">
            <RouterLink
              :to="item.path"
              class="sb__item"
              :class="{ 'sb__item--active': route.path === item.path }"
            >
              <span class="sb__chap">{{ item.chap }}</span>
              <Icon :name="item.icon" :size="15" class="sb__icon" />
              <span class="sb__name">{{ item.label }}</span>
              <span class="sb__act-bar" v-if="route.path === item.path"></span>
            </RouterLink>
          </li>
        </ul>
      </nav>
    </div>
    <footer class="sb__foot">
      <div class="sb__foot-line">论文演示版</div>
      <div class="sb__foot-mono">v1.0 · build 2026</div>
    </footer>
  </aside>
</template>

<style scoped>
.sb {
  width: var(--sidebar-w);
  flex-shrink: 0;
  background: var(--paper-deep);
  border-right: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--topbar-h));
  position: relative;
}
.sb::before {
  content: '';
  position: absolute;
  top: 0; bottom: 0; right: -1px;
  width: 1px;
  background: linear-gradient(to bottom,
    transparent 0,
    var(--rule) 12%,
    var(--rule) 88%,
    transparent 100%);
}

.sb__inner {
  flex: 1;
  overflow-y: auto;
  padding: var(--gap-5) 0 var(--gap-4);
}

.sb__group + .sb__group { margin-top: var(--gap-5); }

.sb__label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 var(--gap-4) 8px;
}
.sb__label-mark {
  width: 6px; height: 6px;
  background: var(--red);
  flex-shrink: 0;
}
.sb__label-zh {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.18em;
  flex-shrink: 0;
}
.sb__label-line {
  flex: 1;
  height: 1px;
  background: var(--rule);
}

.sb__list {
  list-style: none;
  margin: 0;
  padding: 0 var(--gap-3);
}

.sb__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px var(--gap-3);
  font-family: var(--serif);
  font-size: var(--fz-sm);
  font-weight: 500;
  color: var(--ink-soft);
  text-decoration: none;
  border-bottom: 1px dotted transparent;
  transition: all var(--dur-fast) var(--ease-paper);
  letter-spacing: 0.05em;
}
.sb__item:hover {
  color: var(--blue);
  background: var(--paper);
  border-bottom-color: var(--rule);
}

.sb__chap {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  min-width: 18px;
  text-align: center;
}
.sb__item:hover .sb__chap { color: var(--red); }

.sb__icon { color: currentColor; opacity: 0.7; }
.sb__name { flex: 1; }

.sb__item--active {
  color: var(--paper);
  background: var(--blue);
  border-bottom-color: var(--ink);
  border: 0;
  font-weight: 700;
}
.sb__item--active .sb__chap { color: var(--red); background: var(--paper); padding: 0 4px; }
.sb__item--active .sb__icon { opacity: 1; color: var(--paper); }

.sb__act-bar {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--red);
}

.sb__foot {
  padding: var(--gap-4);
  border-top: 1px solid var(--rule);
  background: var(--paper);
  text-align: center;
}
.sb__foot-line {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--blue);
  letter-spacing: 0.2em;
  margin-bottom: 4px;
}
.sb__foot-mono {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.1em;
}
</style>
