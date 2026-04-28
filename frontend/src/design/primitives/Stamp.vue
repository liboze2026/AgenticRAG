<script setup lang="ts">
withDefaults(defineProps<{
  text?: string
  size?: number
  rotate?: number
  variant?: 'red' | 'blue' | 'ink'
}>(), {
  text: '研究\n报告',
  size: 90,
  rotate: -12,
  variant: 'red',
})
</script>

<template>
  <div
    class="stamp"
    :class="[`stamp--${variant}`]"
    :style="{
      width: size + 'px',
      height: size + 'px',
      transform: `rotate(${rotate}deg)`,
      fontSize: (size * 0.18) + 'px',
    }"
  >
    <span class="stamp__text">{{ text }}</span>
  </div>
</template>

<style scoped>
.stamp {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-family: var(--serif);
  font-weight: 900;
  letter-spacing: 0.1em;
  background: rgba(255, 250, 240, 0.45);
  text-align: center;
  line-height: 1.05;
  opacity: 0.86;
  white-space: pre-line;
  user-select: none;
  animation: stamp-down var(--dur-slow) var(--ease-paper) both;
}
.stamp::before, .stamp::after {
  content: '';
  position: absolute; left: 8%; right: 8%; top: 50%;
  height: 1.5px;
  background: currentColor;
  opacity: 0.45;
}
.stamp::after { transform: rotate(90deg); }

.stamp--red { color: var(--red); border: 2.5px solid var(--red); }
.stamp--blue { color: var(--blue); border: 2.5px solid var(--blue); }
.stamp--ink { color: var(--ink); border: 2px solid var(--ink); }

.stamp__text {
  position: relative;
  z-index: 1;
}
</style>
