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
        <span class="col-available">{{ pkg.available || '-' }}</span>
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

function rowClass(pkg) {
  return {
    'row-update': pkg.status === 'update_available',
    'row-missing': pkg.status === 'not_installed',
  }
}

function statusClass(pkg) {
  return {
    'status-ok': pkg.status === 'up_to_date',
    'status-update': pkg.status === 'update_available',
    'status-missing': pkg.status === 'not_installed' || pkg.status === 'not_in_source',
  }
}

function statusText(pkg) {
  const map = {
    up_to_date: 'Up to date',
    update_available: '▲ Update',
    not_in_source: 'Not in source',
    not_installed: 'Not installed',
  }
  return map[pkg.status] || pkg.status
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
  transition: background 0.15s;
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

.col-name { flex: 2; font-weight: 500; }
.col-installed { flex: 1; }
.col-available { flex: 1; }
.col-status { flex: 1; text-align: right; font-weight: 500; }

.status-ok { color: var(--accent-green); }
.status-update { color: #e65100; }
.status-missing { color: var(--text-secondary); }

.table-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
}
</style>
