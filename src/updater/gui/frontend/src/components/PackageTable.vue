<template>
  <div class="package-table">
    <div class="table-header">
      <span class="col-name">Package</span>
      <span class="col-installed">Installed</span>
      <span class="col-available">Available</span>
      <span class="col-status">Status</span>
    </div>
    <div class="table-body">
      <div
        v-for="pkg in packages"
        :key="pkg.name"
        class="table-row"
        :class="rowClass(pkg)"
      >
        <span class="col-name">{{ pkg.name }}</span>
        <span class="col-installed">{{ pkg.installed || '-' }}</span>
        <span class="col-available">
          <select
            :id="`version-${pkg.name}`"
            v-model="store.selectedVersions[pkg.name]"
            :disabled="store.isUpdating"
            @change="onVersionSelect(pkg)"
          >
            <option
              v-for="ver in (store.versionsMap[pkg.name] || [])"
              :key="ver"
              :value="ver"
            >{{ ver }}</option>
            <option v-if="!store.versionsMap[pkg.name] || store.versionsMap[pkg.name].length === 0" :value="null">-</option>
          </select>
        </span>
        <span class="col-status" :class="statusClass(pkg)">
          {{ statusText(pkg) }}
        </span>
      </div>
      <div v-if="packages.length === 0" class="table-empty">
        No packages loaded
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'

const store = inject('store')
const packages = computed(() => store.packages)

function onVersionSelect(pkg) {
  const selected = store.selectedVersions[pkg.name]
  console.log('[PackageTable] Version selected:', selected, 'for', pkg.name, '(installed:', pkg.installed, ')')

  if (selected && selected !== pkg.installed) {
    store.pendingVersionInstall = {
      packageName: pkg.name,
      version: selected,
      installedVersion: pkg.installed,
    }
    store.showVersionModal = true
    console.log('[PackageTable] Opening confirm modal:', pkg.name, pkg.installed, '->', selected)
  }
}

function getEffectiveStatus(pkg) {
  const selected = store.selectedVersions[pkg.name]
  if (pkg.status === 'up_to_date' && selected && selected !== pkg.installed) {
    return 'version_specified'
  }
  return pkg.status
}

function rowClass(pkg) {
  const status = getEffectiveStatus(pkg)
  return {
    'row-update': status === 'update_available',
    'row-missing': status === 'not_installed',
    'row-specified': status === 'version_specified',
    'row-refreshing': store.isUpdating,
  }
}

function statusClass(pkg) {
  const status = getEffectiveStatus(pkg)
  return {
    'status-ok': status === 'up_to_date',
    'status-update': status === 'update_available',
    'status-missing': status === 'not_installed' || status === 'not_in_source',
    'status-specified': status === 'version_specified',
  }
}

function statusText(pkg) {
  const map = {
    up_to_date: 'Up to date',
    update_available: '▲ Update',
    not_in_source: 'Not in source',
    not_installed: 'Not installed',
    version_specified: '⬇ Version specified',
  }
  return map[getEffectiveStatus(pkg)] || getEffectiveStatus(pkg)
}
</script>

<style scoped>
.package-table {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.table-header {
  display: flex;
  background: #e3f2fd;
  padding: 8px 12px;
  font-weight: 600;
  color: var(--accent-blue);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 2px solid var(--accent-blue);
}

.table-body {
  flex: 1;
  overflow-y: auto;
}

.table-row {
  display: flex;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s, background-color 0.5s ease;
}

.row-refreshing {
  background-color: #e8f5e9;
  animation: refresh-pulse 0.8s ease-out;
}

@keyframes refresh-pulse {
  0%   { background-color: #c8e6c9; }
  100% { background-color: #e8f5e9; }
}

.table-row:hover {
  background: #f0f4f8;
}

.row-update {
  background: var(--row-highlight);
}

.row-missing {
  background: #fff3e0;
}

.row-specified {
  background: #f3e5f5;
}

.col-name { flex: 2; font-weight: 500; }
.col-installed { flex: 1; }
.col-available { flex: 1; display: flex; align-items: center; }
.col-status { flex: 1; text-align: right; font-weight: 500; }

.col-available select {
  width: 100%;
  padding: 3px 6px;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  font-size: 12px;
  font-family: var(--font-family);
  background: white;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  color: var(--text-primary);
}

.col-available select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #f5f5f5;
}

.col-available select:hover:not(:disabled) {
  background: #f9f9f9;
  border-color: var(--accent-blue);
}

.status-ok { color: var(--accent-green); }
.status-update { color: #e65100; }
.status-missing { color: var(--text-secondary); }
.status-specified { color: #6a1b9a; }

.table-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
}
</style>
