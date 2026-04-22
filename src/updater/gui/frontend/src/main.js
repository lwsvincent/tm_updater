import { createApp, reactive } from 'vue'
import App from './App.vue'

const store = reactive({
  packages: [],
  logs: [],
  config: {},
  updateComplete: false,
  updateResult: null,
  isUpdating: false,
  isLaunching: false,
})

window.addLogLine = (entry) => {
  store.logs.push(entry)
}

window.onUpdateComplete = (result) => {
  store.updateComplete = true
  store.updateResult = result
  store.isUpdating = false
}

window.updatePackages = (packages) => {
  store.packages = packages
}

window.addEventListener('pywebviewready', async () => {
  store.config = await window.pywebview.api.get_config()
  const packages = await window.pywebview.api.get_packages()
  if (packages && packages.length) {
    store.packages = packages
  }
})

const app = createApp(App)
app.provide('store', store)
app.mount('#app')
