<template>
  <div class="action-panel">
    <div class="actions">
      <button
        class="btn btn-primary"
        :disabled="store.isUpdating || store.isScanning"
        @click="handlePrimaryAction"
      >
        <span v-if="store.isUpdating || store.isScanning" class="spinner"></span>
        {{ primaryButtonText }}
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
import { inject, computed, watch, onMounted } from 'vue'

const store = inject('store')

const updateCount = computed(() => {
  const actionable = store.packages.filter(p =>
    p.status === 'update_available' || p.status === 'not_installed'
  )
  console.log(
    `[ActionPanel] updateCount=${actionable.length}`,
    store.packages.map(p => `${p.name}:${p.status}`)
  )
  return actionable.length
})

const canLaunch = computed(() => {
  return store.updateComplete
    && !store.isLaunching
    && store.config.launcher_executable
})

const primaryButtonText = computed(() => {
  let text
  if (store.isScanning) text = 'Checking...'
  else if (store.isUpdating) text = 'Updating...'
  else if (updateCount.value > 0) text = '↻ Update All'
  else text = '↻ Check for Updates'
  console.log(
    `[ActionPanel] primaryButtonText="${text}"`,
    `isScanning=${store.isScanning}`,
    `isUpdating=${store.isUpdating}`,
    `updateCount=${updateCount.value}`
  )
  return text
})

watch(() => store.isScanning, (val) => {
  console.log(`[ActionPanel] isScanning changed → ${val}`)
})

watch(() => store.isUpdating, (val) => {
  console.log(`[ActionPanel] isUpdating changed → ${val}`)
})

watch(() => store.packages, (pkgs) => {
  console.log(
    `[ActionPanel] packages updated (${pkgs.length} total):`,
    pkgs.map(p => `${p.name}=${p.status}`)
  )
}, { deep: true })

onMounted(() => {
  console.log(
    '[ActionPanel] mounted — initial state:',
    `isScanning=${store.isScanning}`,
    `isUpdating=${store.isUpdating}`,
    `packages=${store.packages.length}`,
    `updateCount=${updateCount.value}`
  )
})

function handlePrimaryAction() {
  if (updateCount.value > 0) {
    runUpdate()
  } else {
    checkForUpdates()
  }
}

async function checkForUpdates() {
  if (store.isScanning || store.isUpdating) return
  store.isScanning = true
  console.log('[ActionPanel] Manual check for updates triggered')
  if (window.pywebview) {
    try {
      await window.pywebview.api.check_for_updates()
    } catch (err) {
      console.error('[ActionPanel] check_for_updates failed:', err)
      store.isScanning = false
    }
  } else {
    setTimeout(() => { store.isScanning = false }, 2000)
  }
}

async function runUpdate() {
  if (store.isUpdating) return
  
  store.isUpdating = true
  store.updateComplete = false
  store.updateResult = null
  // We keep logs or clear them based on preference, clearing is usually better for new runs
  store.logs = [] 
  
  if (window.pywebview) {
    try {
      await window.pywebview.api.run_update()
    } catch (err) {
      console.error('Failed to trigger update:', err)
      store.isUpdating = false
    }
  } else {
    // Mock for browser testing
    setTimeout(() => { store.isUpdating = false }, 2000)
  }
}

async function launchApp() {
  store.isLaunching = true
  if (window.pywebview) {
    const result = await window.pywebview.api.launch_app()
    if (!result.success) {
      store.isLaunching = false
    } else {
      setTimeout(() => { store.isLaunching = false }, 2000)
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
