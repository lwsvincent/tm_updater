<template>
  <div v-if="store.showVersionModal" class="modal-overlay">
    <div class="modal-dialog">
      <h2>Install Different Version?</h2>
      <p v-if="store.pendingVersionInstall">
        <strong>{{ store.pendingVersionInstall.packageName }}</strong>:
        {{ store.pendingVersionInstall.installedVersion || 'not installed' }}
        &rarr; <strong>{{ store.pendingVersionInstall.version }}</strong><br>
        This will uninstall the current version first.
      </p>
      <div class="modal-buttons">
        <button class="btn btn-cancel" :disabled="store.isUpdating" @click="cancelInstall">
          Cancel
        </button>
        <button class="btn btn-confirm" :disabled="store.isUpdating" @click="confirmInstall">
          {{ store.isUpdating ? 'Installing...' : 'Install' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'

const store = inject('store')

function cancelInstall() {
  if (store.pendingVersionInstall) {
    const { packageName, installedVersion } = store.pendingVersionInstall
    store.selectedVersions[packageName] = installedVersion || null
    console.log('[VersionConfirmModal] Cancelled, reset selectedVersions[' + packageName + '] to', installedVersion)
  }
  store.showVersionModal = false
  store.pendingVersionInstall = null
}

async function confirmInstall() {
  if (!store.pendingVersionInstall) return

  const { packageName, version } = store.pendingVersionInstall

  // Lock the UI while waiting for the backend to complete
  store.isUpdating = true

  if (window.pywebview) {
    try {
      // Backend runs install on a background thread and calls
      // window.onVersionedInstallComplete() when done (success or failure).
      await window.pywebview.api.install_versioned_package(packageName, version)
    } catch (err) {
      console.error('[VersionConfirmModal] install_versioned_package call failed:', err)
      store.isUpdating = false
      store.showVersionModal = false
      store.pendingVersionInstall = null
    }
  }
  // Do NOT close the modal here; onVersionedInstallComplete will close it
  // after refreshing package data.
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-dialog {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  padding: 24px;
  min-width: 300px;
  max-width: 500px;
}

.modal-dialog h2 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.modal-dialog p {
  margin: 0 0 20px 0;
  font-size: 14px;
  color: #555;
  line-height: 1.5;
}

.modal-buttons {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.btn {
  padding: 10px 16px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-cancel {
  background: #e0e0e0;
  color: #333;
}

.btn-cancel:hover {
  background: #d0d0d0;
}

.btn-confirm {
  background: #2e7d32;
  color: white;
}

.btn-confirm:hover {
  background: #1b5e20;
}
</style>
