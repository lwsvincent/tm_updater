<template>
  <div class="action-panel">
    <div class="actions">
      <button
        class="btn btn-primary"
        :disabled="store.isUpdating"
        @click="runUpdate"
      >
        <span v-if="store.isUpdating" class="spinner"></span>
        {{ store.isUpdating ? 'Updating...' : '&#8635; Update All' }}
      </button>
      <button
        class="btn btn-success"
        :disabled="!canLaunch"
        @click="launchApp"
      >
        {{ store.isLaunching ? 'Running...' : '&#9654; Launch' }}
      </button>
    </div>
    <div class="status-bar" v-if="store.updateResult">
      <div class="status-item">
        <span class="status-label">Updated</span>
        <span class="status-value ok">{{ store.updateResult.updated }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">Failed</span>
        <span class="status-value" :class="store.updateResult.failed > 0 ? 'fail' : 'ok'">
          {{ store.updateResult.failed }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'

const store = inject('store')

const canLaunch = computed(() => {
  return store.updateComplete
    && !store.isLaunching
    && store.config.launcher_enabled
    && store.config.launcher_executable
})

async function runUpdate() {
  store.isUpdating = true
  store.updateComplete = false
  store.updateResult = null
  store.logs = []
  if (window.pywebview) {
    await window.pywebview.api.run_update()
  }
}

async function launchApp() {
  store.isLaunching = true
  if (window.pywebview) {
    const result = await window.pywebview.api.launch_app()
    if (!result.success) {
      store.isLaunching = false
    }
  }
}
</script>

<style scoped>
.action-panel {
  padding: 12px;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn {
  padding: 10px 16px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s;
  font-family: var(--font-family);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--accent-blue);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0d47a1;
}

.btn-success {
  background: #2e7d32;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #1b5e20;
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-bar {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  padding: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 4px;
}

.status-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.status-label {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
}

.status-value {
  font-size: 18px;
  font-weight: 700;
}

.status-value.ok { color: var(--accent-green); }
.status-value.fail { color: var(--accent-red); }
</style>
