<script setup lang="ts">
interface Column {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  numeric?: boolean
  width?: string
}
withDefaults(defineProps<{
  columns: Column[]
  rows: Record<string, any>[]
  rowKey?: string
  empty?: string
  hover?: boolean
}>(), {
  rowKey: 'id',
  empty: '暂无记录',
  hover: true,
})
defineEmits<{
  (e: 'rowClick', row: Record<string, any>, idx: number): void
}>()
</script>

<template>
  <div class="tbl-wrap">
    <table class="tbl" :class="{ 'tbl--hover': hover }">
      <colgroup>
        <col v-for="c in columns" :key="c.key" :style="{ width: c.width }" />
      </colgroup>
      <thead>
        <tr>
          <th
            v-for="c in columns"
            :key="c.key"
            :class="{
              'tbl__num': c.numeric,
              [`tbl__al-${c.align}`]: c.align,
            }"
          >{{ c.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="row[rowKey] ?? i" @click="$emit('rowClick', row, i)">
          <td
            v-for="c in columns"
            :key="c.key"
            :class="{
              'tbl__num': c.numeric,
              [`tbl__al-${c.align}`]: c.align,
            }"
          >
            <slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]" :idx="i">
              {{ row[c.key] }}
            </slot>
          </td>
        </tr>
        <tr v-if="!rows.length" class="tbl__empty-row">
          <td :colspan="columns.length" class="tbl__empty">{{ empty }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tbl-wrap { overflow-x: auto; border: 1px solid var(--rule); background: var(--paper); }
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--serif);
  font-size: var(--fz-sm);
}

.tbl thead th {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono-sm);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  color: var(--ink-mute);
  text-align: left;
  padding: 10px 14px;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--ink);
  background: var(--paper-deep);
  white-space: nowrap;
}

.tbl tbody td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--rule-fine);
  color: var(--ink);
  vertical-align: middle;
}
.tbl tbody tr:last-child td { border-bottom: none; }
.tbl--hover tbody tr:hover td { background: var(--blue-tint); cursor: pointer; }

.tbl__num { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; }
.tbl__al-center { text-align: center; }
.tbl__al-right { text-align: right; }

.tbl__empty {
  text-align: center;
  padding: 40px 14px;
  color: var(--ink-mute);
  font-style: italic;
  background: var(--paper);
}
.tbl__empty-row:hover td { background: var(--paper) !important; cursor: default; }
</style>
