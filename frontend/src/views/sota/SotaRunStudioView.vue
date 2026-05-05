<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sotaApi } from '../../api/sota'

const router = useRouter()
const subsets = ref<string[]>([])
const methods = ref<{ name: string; description: string }[]>([])
const subsetSel = ref<Record<string, boolean>>({})
const methodSel = ref<Record<string, boolean>>({})
const topK = ref(10)
const scale = ref<'quick' | 'standard' | 'full'>('quick')
const notes = ref('')
const submitting = ref(false)
const errMsg = ref('')

async function load() {
  const ds = await sotaApi.datasets()
  if (ds.ok) {
    subsets.value = Object.keys(ds.subsets)
    for (const s of subsets.value) {
      subsetSel.value[s] = ds.subsets[s].status === 'ok'
    }
  }
  const ms = await sotaApi.methods()
  if (ms.ok) {
    methods.value = ms.methods
    for (const m of methods.value) methodSel.value[m.name] = true
  }
}
onMounted(load)

async function launch() {
  submitting.value = true
  errMsg.value = ''
  const n = scale.value === 'quick' ? 50 : scale.value === 'standard' ? 200 : null
  const body = {
    subsets: subsets.value.filter(s => subsetSel.value[s]),
    methods: methods.value.map(m => m.name).filter(m => methodSel.value[m]),
    top_k: topK.value,
    n_queries_per_subset: n,
    notes: notes.value,
  }
  if (body.subsets.length === 0) {
    errMsg.value = '请至少选择一个子集'
    submitting.value = false
    return
  }
  if (body.methods.length === 0) {
    errMsg.value = '请至少选择一个方法'
    submitting.value = false
    return
  }
  try {
    const r = await sotaApi.createRun(body)
    if (r.ok) {
      router.push(`/sota/runs/${r.run_id}`)
    } else {
      errMsg.value = r.message || r.error_kind || ''
    }
  } catch (e: any) {
    errMsg.value = e?.message || String(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1>实验台</h1>
    <p class="hint">
      选择子集 × 方法 × 规模 → 后台启动 run, 完成后排行榜自动收录。
      Quick = 每子集 50 query (~分钟级), Standard = 200 (~10 分钟),
      Full = 测试集全部 (按子集大小可能数小时)。
    </p>

    <section>
      <h3>子集</h3>
      <label v-for="s in subsets" :key="s" class="chk">
        <input type="checkbox" v-model="subsetSel[s]"> {{ s }}
      </label>
    </section>

    <section>
      <h3>方法</h3>
      <label v-for="m in methods" :key="m.name" class="chk" :title="m.description">
        <input type="checkbox" v-model="methodSel[m.name]"> {{ m.name }}
      </label>
    </section>

    <section>
      <h3>规模</h3>
      <label class="chk"><input type="radio" v-model="scale" value="quick"> Quick (50/子集)</label>
      <label class="chk"><input type="radio" v-model="scale" value="standard"> Standard (200/子集)</label>
      <label class="chk"><input type="radio" v-model="scale" value="full"> Full (test 全集)</label>
    </section>

    <section>
      <h3>top-k</h3>
      <input type="number" v-model.number="topK" min="1" max="50" class="num">
    </section>

    <section>
      <h3>备注</h3>
      <input type="text" v-model="notes" placeholder="选填; 写明本次实验的目的" class="txt">
    </section>

    <button class="btn" @click="launch" :disabled="submitting">
      {{ submitting ? '启动中…' : '启动实验' }}
    </button>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
  </div>
</template>

<style scoped>
.page { padding: 24px; max-width: 760px; }
.hint { color: #888; font-size: 13px; margin-bottom: 16px; }
section { margin-bottom: 16px; }
h3 { font-size: 13px; margin: 0 0 6px 0; color: #ccc; text-transform: uppercase;
     letter-spacing: 0.5px; }
.chk { display: inline-block; margin-right: 14px; cursor: pointer; }
.num { width: 80px; padding: 4px 8px; border-radius: 4px; border: 1px solid #2a2f36;
       background: #1a1f26; color: #eee; }
.txt { width: 100%; max-width: 480px; padding: 6px 10px; border-radius: 4px;
       border: 1px solid #2a2f36; background: #1a1f26; color: #eee; }
.btn { padding: 8px 18px; border-radius: 6px; border: 1px solid #4a8ff7;
       background: #1a3a6a; color: #fff; cursor: pointer; font-weight: 600; }
.btn:disabled { opacity: 0.6; cursor: wait; }
.err { color: #f87171; margin-top: 10px; }
</style>
