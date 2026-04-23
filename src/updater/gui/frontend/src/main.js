import { createApp, reactive } from 'vue'
import App from './App.vue'

const store = reactive({
  packages: [],
  logs: [],
  config: {}, // Use empty object to prevent property access errors
  updateComplete: false,
  updateResult: null,
  isUpdating: false,
  isLaunching: false,
})

let configResolver;
const configPromise = new Promise((resolve) => {
  configResolver = resolve;
});

window.addLogLine = (entry) => {
  store.logs.push(entry)
  if (store.logs.length > 1000) {
    store.logs.shift()
  }
}

window.onUpdateComplete = (result) => {
  store.updateComplete = true
  store.updateResult = result
  store.isUpdating = false
}

window.onScanComplete = async (hasUpdates) => {
  console.log('[DEBUG] onScanComplete called. hasUpdates:', hasUpdates);
  
  // Wait for config to be loaded before making automation decisions
  await configPromise;
  console.log('[DEBUG] Config is ready in onScanComplete:', store.config);
  
  if (!hasUpdates) {
    store.updateComplete = true
  }
  
  const shouldAutoUpdate = hasUpdates && (store.config.auto_update || store.config.auto_update_enable);
  console.log('[DEBUG] Should auto update?', shouldAutoUpdate);

  if (shouldAutoUpdate) {
    console.log('[DEBUG] Triggering auto update...');
    store.isUpdating = true // Set state here
    window.pywebview.api.run_update()
  } else if (!hasUpdates && (store.config.auto_launch || store.config.auto_launch_enable)) {
    console.log('[DEBUG] No updates, checking auto launch...');
    window.pywebview.api.launch_app()
  }
}

window.updatePackages = (packages) => {
  console.log('[DEBUG] Packages updated:', packages.length, 'packages');
  store.packages = packages
}

window.addEventListener('pywebviewready', async () => {
  console.log('[DEBUG] pywebviewready triggered');
  
  // 1. Get config first
  const config = await window.pywebview.api.get_config()
  console.log('[DEBUG] Received config from backend:', config);
  store.config = config
  configResolver(config) // Signal that config is ready (for onScanComplete)
  
  // 2. Get initial package list
  const packages = await window.pywebview.api.get_packages()
  if (packages && packages.length) {
    store.packages = packages
  }

  // 3. NOW trigger the scan from frontend
  console.log('[DEBUG] Triggering check_for_updates from frontend');
  window.pywebview.api.check_for_updates()
})

const app = createApp(App)
app.provide('store', store)
app.mount('#app')
