<template>
  <div v-if="store.showVersionModal" class="modal-overlay">
    <div class="modal-dialog">
      <h2>Install Different Version?</h2>
      <p v-if="store.pendingVersionInstall">
        Install version <strong>{{ store.pendingVersionInstall.version }}</strong>?
        This will uninstall the current version first.
      </p>
      <div class="modal-buttons">
        <button class="btn btn-cancel" @click="cancelInstall">
          Cancel
        </button>
        <button class="btn btn-confirm" @click="confirmInstall">
          Install
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'

const store = inject('store')

function cancelInstall() {
  store.showVersionModal = false
  store.pendingVersionInstall = null
}

function confirmInstall() {
  // Task 10 will implement actual install logic here
  console.log(`[Task 10] Will install: ${store.pendingVersionInstall.packageName}@${store.pendingVersionInstall.version}`)
  store.showVersionModal = false
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
