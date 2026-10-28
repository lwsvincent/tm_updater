<template>
  <div class="target-bar">
    <div class="target-info">
      <span class="target-label">目標資料夾</span>
      <span class="target-path" :title="store.target.project || ''">
        {{ store.target.project || '（未解析）' }}
      </span>
      <span class="target-meta" :title="store.target.venv || ''">
        venv: {{ shorten(store.target.venv) || '未找到' }}
      </span>
      <span class="target-meta" :title="store.target.source || ''">
        source: {{ shorten(store.target.source) }}
      </span>
      <span
        v-if="store.target.config_origin"
        class="target-origin"
        :class="store.target.config_origin === 'project' ? 'from-project' : 'from-exe'"
        :title="store.target.config"
      >
        設定: {{ store.target.config_origin }}
      </span>
    </div>
    <div class="target-controls">
      <input
        v-model="draft"
        class="target-input"
        type="text"
        placeholder="輸入或選擇要更新的專案資料夾"
        :title="draft"
        @keyup.enter="apply"
      />
      <button class="btn btn-small" :disabled="busy || !draft" @click="apply">套用</button>
      <button class="btn btn-small btn-browse" :disabled="busy" @click="browse">瀏覽…</button>
    </div>
    <div v-if="error" class="target-error">{{ error }}</div>
    <div v-if="store.target.error" class="target-error">{{ store.target.error }}</div>
    <div v-if="store.target.config_error" class="target-error warn">
      {{ store.target.config_error }}
      <span v-if="store.target.encoding" class="target-meta">
        （編碼: {{ store.target.encoding }}）
      </span>
    </div>
  </div>
</template>

<script setup>
import { inject, ref, watch } from 'vue'

const store = inject('store')
const reloadTarget = inject('reloadTarget')

const draft = ref('')
const busy = ref(false)
const error = ref('')

// Prefill once the backend reports the resolved target (arrives after mount).
watch(
  () => store.target.project,
  (project) => {
    if (!draft.value && project) draft.value = project
  },
  { immediate: true }
)

function shorten(path) {
  if (!path) return ''
  return path.length > 48 ? '…' + path.slice(-47) : path
}

async function applyPath(path) {
  if (!window.pywebview) return
  busy.value = true
  error.value = ''
  try {
    const result = await window.pywebview.api.set_target(path)
    if (result.error) {
      error.value = result.error
    } else {
      store.target = result.target
      draft.value = result.target.project
      if (reloadTarget) await reloadTarget()
    }
  } catch (err) {
    error.value = String(err)
  } finally {
    busy.value = false
  }
}

function apply() {
  if (draft.value.trim()) applyPath(draft.value.trim())
}

async function browse() {
  if (!window.pywebview) return
  busy.value = true
  error.value = ''
  try {
    const result = await window.pywebview.api.choose_target_folder()
    if (result.cancelled) return
    if (result.error) {
      error.value = result.error
      return
    }
    store.target = result.target
    draft.value = result.target.project
    if (reloadTarget) await reloadTarget()
  } catch (err) {
    error.value = String(err)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.target-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 6px 20px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
}

.target-info {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
  flex: 1 1 320px;
}

.target-label {
  color: var(--text-secondary);
  font-weight: 600;
  white-space: nowrap;
}

.target-path {
  font-family: var(--font-mono);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 46vw;
}

.target-meta {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  white-space: nowrap;
}

.target-origin {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.from-project {
  background: var(--accent-green);
  color: #fff;
}

.from-exe {
  background: var(--accent-orange);
  color: #fff;
}

.target-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 1 auto;
}

.target-input {
  width: 260px;
  padding: 4px 6px;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 12px;
}

.btn-small {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  background: var(--bg-primary);
  cursor: pointer;
}

.btn-browse {
  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
}

.target-error {
  flex-basis: 100%;
  color: var(--accent-red);
  font-size: 12px;
}

.target-error.warn {
  color: var(--accent-orange);
}
</style>
