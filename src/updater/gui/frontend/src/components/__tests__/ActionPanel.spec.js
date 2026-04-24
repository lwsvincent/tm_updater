import { describe, it, expect, beforeEach, vi } from 'vitest'
import { reactive } from 'vue'
import { mount } from '@vue/test-utils'
import ActionPanel from '../ActionPanel.vue'

describe('ActionPanel.vue', () => {
  let store

  beforeEach(() => {
    store = reactive({
      packages: [],
      isUpdating: false,
      isLaunching: false,
      updateComplete: false,
      updateResult: null,
      config: {},
      logs: [],
      showVersionModal: false,
      pendingVersionInstall: null,
      versionsMap: {},
      selectedVersions: {},
    })
    window.pywebview = {
      api: {
        run_update: vi.fn().mockResolvedValue({}),
        launch_app: vi.fn().mockResolvedValue({ success: true }),
      },
    }
  })

  function mountPanel() {
    return mount(ActionPanel, { global: { provide: { store } } })
  }

  // Install Selected Version button no longer exists — version selection is
  // triggered by the dropdown in PackageTable.vue (see PackageTable.refresh.spec.js).

  // -------------------------------------------------------------------
  // Update All button
  // -------------------------------------------------------------------

  it('test_update_button_disabled_when_is_updating', () => {
    store.packages = [{ name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' }]
    store.isUpdating = true

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-primary')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('test_update_button_disabled_when_no_updates_available', () => {
    store.packages = [{ name: 'pkg-a', installed: '1.0.0', available: '1.0.0', status: 'up_to_date' }]

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-primary')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('test_update_button_enabled_when_updates_available', () => {
    store.packages = [{ name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' }]

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-primary')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('test_update_button_enabled_when_package_not_installed', () => {
    store.packages = [{ name: 'pkg-a', installed: null, available: '1.0.0', status: 'not_installed' }]

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-primary')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('test_clicking_update_sets_is_updating', async () => {
    store.packages = [{ name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' }]
    window.pywebview.api.run_update = vi.fn(() => new Promise(() => {}))

    const wrapper = mountPanel()
    await wrapper.find('.btn-primary').trigger('click')

    expect(store.isUpdating).toBe(true)
  })

  it('test_clicking_update_calls_run_update_api', async () => {
    store.packages = [{ name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' }]

    const wrapper = mountPanel()
    await wrapper.find('.btn-primary').trigger('click')
    await new Promise((r) => setTimeout(r, 0))

    expect(window.pywebview.api.run_update).toHaveBeenCalled()
  })

  // -------------------------------------------------------------------
  // Status bar
  // -------------------------------------------------------------------

  it('test_status_bar_hidden_when_no_result', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('.status-bar').exists()).toBe(false)
  })

  it('test_status_bar_shows_updated_count', async () => {
    store.updateResult = { total: 3, updated: 2, failed: 1 }

    const wrapper = mountPanel()
    expect(wrapper.find('.status-bar').exists()).toBe(true)
    expect(wrapper.text()).toContain('2')
  })
})
