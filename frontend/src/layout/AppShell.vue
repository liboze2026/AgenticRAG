<script setup lang="ts">
import TopBar from './TopBar.vue'
import SideBar from './SideBar.vue'
</script>

<template>
  <div class="shell">
    <TopBar />
    <div class="shell__body">
      <SideBar />
      <main class="shell__main">
        <div class="shell__sheet">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--paper);
}

.shell__body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.shell__main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  height: calc(100vh - var(--topbar-h));
  padding: var(--gap-6) var(--gap-7);
  position: relative;
}
.shell__main::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 8px;
  background:
    repeating-linear-gradient(90deg,
      var(--rule-fine) 0, var(--rule-fine) 1px,
      transparent 1px, transparent 8px);
  opacity: 0.5;
  pointer-events: none;
}

.shell__sheet {
  max-width: var(--content-max);
  margin: 0 auto;
  position: relative;
  padding-top: var(--gap-3);
}
</style>
