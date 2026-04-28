<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { datasetsApi, type DatasetInfo } from '../api/client'
import {
  AppPageHead, AppCard, AppInput, AppButton, AppTable, msg,
} from '../design/primitives'
import Icon from '../design/Icons.vue'

const datasets = ref<DatasetInfo[]>([])
const newName = ref('')
const newDesc = ref('')
const loading = ref(false)
const creating = ref(false)

async function refresh() {
  loading.value = true
  try {
    const resp = await datasetsApi.list()
    datasets.value = resp.data
  } catch {}
  loading.value = false
}

async function create() {
  if (!newName.value.trim()) {
    msg.warn('请填写集录名称')
    return
  }
  creating.value = true
  try {
    await datasetsApi.create(newName.value.trim(), newDesc.value.trim())
    newName.value = ''
    newDesc.value = ''
    msg.success('已建立集录')
    await refresh()
  } finally { creating.value = false }
}

async function handleDelete(id: number) {
  if (!confirm('确认注销此集录？')) return
  await datasetsApi.delete(id)
  msg.success('已注销')
  await refresh()
}

const cols = [
  { key: 'id', label: '编号', width: '70px', numeric: true },
  { key: 'name', label: '集录名称', width: '220px' },
  { key: 'description', label: '描述' },
  { key: 'document_count', label: '文献数', width: '90px', numeric: true },
  { key: 'created_at', label: '建立时间', width: '180px' },
  { key: 'ops', label: '操作', width: '100px', align: 'center' as const },
]

function formatTime(iso: string) {
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}.${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getDate().toString().padStart(2,'0')}`
  } catch { return iso }
}

onMounted(refresh)
</script>

<template>
  <div class="dsv">
    <AppPageHead
      chapter="4"
      kicker="corpora · 语 料"
      title="语 料 集 录"
      subtitle="编纂评测集录 · 用于实验复现与跨流水线对比"
      stamp="集录&#10;管理"
    />

    <AppCard title="新 建 集 录" subtitle="register new corpus" :num="'A'">
      <div class="dsv-form">
        <div class="dsv-form__row">
          <label class="dsv-form__l">名　称</label>
          <div class="dsv-form__f">
            <AppInput v-model="newName" placeholder="例 · baseline-v1" />
          </div>
        </div>
        <div class="dsv-form__row">
          <label class="dsv-form__l">描　述</label>
          <div class="dsv-form__f">
            <AppInput v-model="newDesc" placeholder="可选 · 简述用途" />
          </div>
        </div>
        <div class="dsv-form__act">
          <AppButton variant="primary" :loading="creating" @click="create">
            <Icon name="plus" :size="13" />
            建 立 集 录
          </AppButton>
        </div>
      </div>
    </AppCard>

    <AppCard title="已 录 集 录" :subtitle="`existing corpora · ${datasets.length} entries`" :num="'B'" class="dsv-list">
      <template #extra>
        <AppButton variant="ghost" size="sm" :loading="loading" @click="refresh">
          <Icon name="reload" :size="13" />
          刷 新
        </AppButton>
      </template>
      <AppTable :columns="cols" :rows="datasets" empty="尚无集录">
        <template #cell-id="{ row }">№ {{ row.id }}</template>
        <template #cell-name="{ row }">
          <span class="dsv-name">{{ row.name }}</span>
        </template>
        <template #cell-description="{ row }">
          <span class="dsv-desc">{{ row.description || '—' }}</span>
        </template>
        <template #cell-created_at="{ row }">{{ formatTime(row.created_at) }}</template>
        <template #cell-ops="{ row }">
          <button class="dsv-del" @click="handleDelete(row.id)" title="注销">
            <Icon name="trash" :size="13" />
          </button>
        </template>
      </AppTable>
    </AppCard>
  </div>
</template>

<style scoped>
.dsv { max-width: 1100px; margin: 0 auto; }

.dsv-form { display: flex; flex-direction: column; gap: var(--gap-3); }
.dsv-form__row {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: var(--gap-4);
  align-items: center;
}
.dsv-form__l {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.18em;
}
.dsv-form__act {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

.dsv-list { margin-top: var(--gap-5); }

.dsv-name {
  font-family: var(--serif);
  font-weight: 700;
  color: var(--blue);
}
.dsv-desc {
  font-family: var(--serif);
  font-style: italic;
  color: var(--ink-soft);
}
.dsv-del {
  width: 28px; height: 28px;
  background: transparent;
  border: 1px solid var(--rule);
  cursor: pointer;
  color: var(--ink-mute);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  transition: all var(--dur-fast);
}
.dsv-del:hover { color: var(--red); border-color: var(--red); }
</style>
