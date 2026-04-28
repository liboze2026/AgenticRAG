<script setup lang="ts">
defineProps<{ name: string; size?: number | string }>()
</script>

<template>
  <svg
    :width="size || 18"
    :height="size || 18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="ic"
    :aria-hidden="true"
  >
    <!-- 基础几何 -->
    <template v-if="name === 'home'"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></template>
    <template v-else-if="name === 'chat'"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></template>
    <template v-else-if="name === 'search'"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/></template>
    <template v-else-if="name === 'doc'"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></template>
    <template v-else-if="name === 'archive'"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></template>
    <template v-else-if="name === 'flask'"><path d="M9 3v6L4 18a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-5-9V3"/><line x1="8" y1="3" x2="16" y2="3"/><line x1="6.5" y1="14" x2="17.5" y2="14"/></template>
    <template v-else-if="name === 'gauge'"><circle cx="12" cy="12" r="9"/><path d="M12 12L7 7"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></template>
    <template v-else-if="name === 'upload'"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></template>
    <template v-else-if="name === 'plus'"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></template>
    <template v-else-if="name === 'minus'"><line x1="5" y1="12" x2="19" y2="12"/></template>
    <template v-else-if="name === 'close'"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></template>
    <template v-else-if="name === 'check'"><polyline points="20 6 9 17 4 12"/></template>
    <template v-else-if="name === 'trash'"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/></template>
    <template v-else-if="name === 'reload'"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></template>
    <template v-else-if="name === 'send'"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></template>
    <template v-else-if="name === 'menu'"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></template>
    <template v-else-if="name === 'eye'"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></template>
    <template v-else-if="name === 'edit'"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></template>
    <template v-else-if="name === 'chevron-down'"><polyline points="6 9 12 15 18 9"/></template>
    <template v-else-if="name === 'chevron-right'"><polyline points="9 6 15 12 9 18"/></template>
    <template v-else-if="name === 'chevron-left'"><polyline points="15 18 9 12 15 6"/></template>
    <template v-else-if="name === 'info'"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><line x1="12" y1="8" x2="12.01" y2="8"/></template>
    <template v-else-if="name === 'warn'"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></template>
    <template v-else-if="name === 'database'"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></template>
    <template v-else-if="name === 'page'"><rect x="4" y="2" width="16" height="20"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="16" y2="11"/><line x1="8" y1="15" x2="13" y2="15"/></template>
    <template v-else-if="name === 'clock'"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></template>
    <template v-else-if="name === 'tag'"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></template>
    <template v-else-if="name === 'filter'"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></template>
    <template v-else-if="name === 'arrow-right'"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></template>
    <template v-else-if="name === 'arrow-left'"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></template>
    <template v-else-if="name === 'spinner'"><path d="M12 3a9 9 0 1 0 9 9" stroke-dasharray="2 3" /></template>
    <template v-else-if="name === 'book'"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></template>
    <template v-else-if="name === 'sparkles'"><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/><path d="M6 6l2 2M16 16l2 2M6 18l2-2M16 8l2-2"/></template>
  </svg>
</template>

<style scoped>
.ic { display: inline-block; vertical-align: middle; flex-shrink: 0; }
</style>
