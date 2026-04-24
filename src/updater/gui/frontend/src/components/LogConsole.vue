<template>
  <div class="log-console">
    <div class="log-header">Console</div>
    <div class="log-body" ref="logBody">
      <div
        v-for="(entry, i) in logs"
        :key="i"
        class="log-line"
        :class="'log-' + entry.level"
      >
        <span class="log-time">{{ entry.timestamp }}</span>
        <span class="log-msg">{{ entry.message }}</span>
      </div>
      <div v-if="logs.length === 0" class="log-empty">
        Waiting for activity...
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed, ref, watch, nextTick } from 'vue'

const store = inject('store')
const logs = computed(() => store.logs)
const logBody = ref(null)

watch(logs, async () => {
  await nextTick()
  if (logBody.value) {
    logBody.value.scrollTop = logBody.value.scrollHeight
  }
}, { deep: true })
</script>

<style scoped>
.log-console {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-top: 2px solid var(--accent-blue);
  margin-top: 12px;
  min-height: 0;
}

.log-header {
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.log-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-log);
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
}

.log-line {
  display: flex;
  gap: 8px;
}

.log-time {
  color: #546e7a;
  flex-shrink: 0;
}

.log-msg {
  color: var(--text-log);
  overflow-wrap: anywhere;
  min-width: 0;
}

.log-info .log-msg { color: #4fc3f7; }
.log-success .log-msg { color: var(--accent-green); }
.log-error .log-msg { color: var(--accent-red); }

.log-empty {
  color: #546e7a;
  font-style: italic;
  padding: 20px 0;
}
</style>
