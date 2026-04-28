<script setup lang="ts">
withDefaults(defineProps<{
  text?: string
  hint?: string
}>(), {
  text: '暂无记录',
})
</script>

<template>
  <div class="empty">
    <div class="empty__deco">
      <span class="empty__circ" v-for="i in 3" :key="i" />
    </div>
    <p class="empty__text">{{ text }}</p>
    <p class="empty__hint" v-if="hint">{{ hint }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty {
  text-align: center;
  padding: var(--gap-7) var(--gap-5);
  color: var(--ink-mute);
}
.empty__deco {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 18px;
}
.empty__circ {
  width: 8px; height: 8px;
  border: 1px solid var(--rule);
  border-radius: 50%;
}
.empty__circ:nth-child(2) { transform: translateY(-3px); }
.empty__text {
  font-family: var(--serif);
  font-style: italic;
  font-size: var(--fz-h4);
  color: var(--ink-mute);
  margin: 0 0 4px;
}
.empty__hint {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  margin: 0 0 var(--gap-4);
}
</style>
