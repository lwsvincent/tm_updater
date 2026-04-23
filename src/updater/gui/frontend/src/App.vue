<template>
  <div class="app">
    <header class="app-header">
      <h1>Test Matrix Updater</h1>
      <div class="header-status">
        <span v-if="updateCount > 0" class="badge badge-update">
          {{ updateCount }} update{{ updateCount > 1 ? 's' : '' }}
        </span>
        <span v-else-if="store.packages.length > 0" class="badge badge-ok">
          All up to date
        </span>
      </div>
    </header>
    <div class="app-body">
      <div class="panel-left">
        <PackageTable />
      </div>
      <div class="panel-right">
        <ActionPanel />
        <LogConsole />
      </div>
    </div>
    <VersionConfirmModal />
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'
import PackageTable from './components/PackageTable.vue'
import ActionPanel from './components/ActionPanel.vue'
import LogConsole from './components/LogConsole.vue'
import VersionConfirmModal from './components/VersionConfirmModal.vue'

const store = inject('store')

const updateCount = computed(() =>
  store.packages.filter(p =>
    p.status === 'update_available' || p.status === 'not_installed'
  ).length
)
</script>

<style>
@import './themes/blueprint.css';

.app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: var(--bg-header);
  color: var(--text-header);
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

.app-header h1 {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.badge {
  padding: 3px 10px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.badge-update {
  background: var(--accent-orange);
  color: white;
}

.badge-ok {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.panel-left {
  flex: 65;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
  background: var(--bg-card);
}

.panel-right {
  flex: 35;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}
</style>
