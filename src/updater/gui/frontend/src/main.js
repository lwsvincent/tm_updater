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
  showVersionModal: false,
  pendingVersionInstall: null, // {packageName: string, version: string}
  versionsMap: {},       // { package_name: ["X.Y.Z", "A.B.C", ...] } sorted newest-first
  selectedVersions: {},  // { package_name: "X.Y.Z" } user's current selection
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

window.onVersionedInstallComplete = async (result) => {
  if (result.success) {
    console.log('[onVersionedInstallComplete] Installation complete')
  } else {
    const failures = result.failures ? result.failures.join(', ') : 'unknown error'
    console.error(`[onVersionedInstallComplete] Install failed: ${failures}`)
  }

  // Refresh package list and versions BEFORE closing the modal so the user
  // sees updated versions when the modal disappears.
  if (window.pywebview) {
    try {
      const pkgData = await window.pywebview.api.get_packages()
      store.packages = pkgData

      // Refresh versions for each package in parallel (same pattern as initial load)
      await Promise.all(pkgData.map(async (pkg) => {
        try {
          const versions = await window.pywebview.api.get_versions(pkg.name)
          store.versionsMap[pkg.name] = versions || []
          // Auto-select the newly installed version
          store.selectedVersions[pkg.name] = pkg.installed || (versions && versions[0]) || null
        } catch (err) {
          console.warn(`[onVersionedInstallComplete] Failed to load versions for ${pkg.name}:`, err)
          store.versionsMap[pkg.name] = []
        }
      }))

      store.pendingVersionInstall = null
      store.showVersionModal = false
    } catch (err) {
      console.error('[onVersionedInstallComplete] Refresh failed:', err)
    }
  } else {
    store.pendingVersionInstall = null
    store.showVersionModal = false
  }

  // Always unlock UI regardless of success or failure
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

  // 3. Load all versions for each package in parallel (fastest at cold start)
  if (packages && packages.length) {
    console.log('[DEBUG] Loading versions for', packages.length, 'package(s)...');
    await Promise.all(packages.map(async (pkg) => {
      try {
        const versions = await window.pywebview.api.get_versions(pkg.name);
        store.versionsMap[pkg.name] = versions || [];
        // Default selection: first entry is newest (backend sorts newest-first)
        store.selectedVersions[pkg.name] = (versions && versions.length > 0)
          ? versions[0]
          : (pkg.available || null);
        console.log('[DEBUG] Versions for', pkg.name, ':', versions);
      } catch (err) {
        console.warn('[DEBUG] Failed to load versions for', pkg.name, ':', err);
        store.versionsMap[pkg.name] = [];
        store.selectedVersions[pkg.name] = pkg.available || null;
      }
    }));
  }

  // 4. NOW trigger the scan from frontend
  console.log('[DEBUG] Triggering check_for_updates from frontend');
  window.pywebview.api.check_for_updates()
})

const app = createApp(App)
app.provide('store', store)
app.mount('#app')
