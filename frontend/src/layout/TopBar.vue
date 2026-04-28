<script setup lang="ts">
import { computed } from 'vue'

const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()} 年 ${(d.getMonth() + 1).toString().padStart(2, '0')} 月 ${d.getDate().toString().padStart(2, '0')} 日`
})
</script>

<template>
  <header class="tb">
    <div class="tb__brand">
      <div class="tb__crest">
        <svg viewBox="0 0 64 64" width="36" height="36" aria-hidden="true">
          <circle cx="32" cy="32" r="29" fill="none" stroke="currentColor" stroke-width="2"/>
          <circle cx="32" cy="32" r="22" fill="none" stroke="currentColor" stroke-width="0.8"/>
          <text x="32" y="40" text-anchor="middle" font-family="serif" font-weight="900" font-size="22" fill="currentColor">研</text>
          <line x1="32" y1="3" x2="32" y2="11" stroke="currentColor" stroke-width="1.5"/>
          <line x1="32" y1="53" x2="32" y2="61" stroke="currentColor" stroke-width="1.5"/>
          <line x1="3" y1="32" x2="11" y2="32" stroke="currentColor" stroke-width="1.5"/>
          <line x1="53" y1="32" x2="61" y2="32" stroke="currentColor" stroke-width="1.5"/>
        </svg>
      </div>
      <div class="tb__name">
        <span class="tb__zh">智 能 体 检 索 增 强</span>
        <span class="tb__en">AGENTIC RETRIEVAL-AUGMENTED GENERATION · v1.0</span>
      </div>
    </div>

    <div class="tb__rule" aria-hidden="true">
      <span class="tb__dot"></span>
      <span class="tb__dot"></span>
      <span class="tb__dot"></span>
    </div>

    <div class="tb__date">
      <span class="tb__date-l">日　期</span>
      <span class="tb__date-v">{{ today }}</span>
    </div>
  </header>
</template>

<style scoped>
.tb {
  display: flex;
  align-items: center;
  height: var(--topbar-h);
  padding: 0 var(--gap-5);
  background: var(--blue-deep);
  color: var(--paper);
  border-bottom: 3px solid var(--ink);
  position: relative;
  z-index: 50;
}
.tb::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: -7px;
  height: 1px;
  background: var(--ink);
}

.tb__brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.tb__crest {
  color: var(--paper);
  background: var(--red);
  border: 1.5px solid var(--paper);
  width: 42px; height: 42px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 0 0 1px var(--ink);
}
.tb__name {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.tb__zh {
  font-family: var(--serif);
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 0.16em;
  color: var(--paper);
}
.tb__en {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: rgba(247, 244, 237, 0.6);
  margin-top: 2px;
}

.tb__rule {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  height: 100%;
  position: relative;
}
.tb__rule::before, .tb__rule::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(247, 244, 237, 0.18);
}
.tb__dot {
  width: 5px; height: 5px;
  background: rgba(247, 244, 237, 0.4);
  border-radius: 50%;
}
.tb__dot:nth-child(2) {
  background: var(--red);
  width: 7px; height: 7px;
  border-radius: 0;
  transform: rotate(45deg);
}

.tb__date {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  text-transform: uppercase;
  letter-spacing: 0.14em;
}
.tb__date-l {
  color: rgba(247, 244, 237, 0.55);
  font-family: var(--serif);
  font-weight: 600;
  text-transform: none;
  letter-spacing: 0.1em;
}
.tb__date-v {
  color: var(--paper);
  font-family: var(--serif);
  font-weight: 500;
  text-transform: none;
}
</style>
