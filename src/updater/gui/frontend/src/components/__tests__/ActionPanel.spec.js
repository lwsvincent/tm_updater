import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ActionPanel from '../ActionPanel.vue'

describe('ActionPanel.vue - Install Selected Version button', () => {
  let store

  beforeEach(() => {
    store = {
      packages: [],
      isUpdating: false,
      isLaunching: false,
      updateComplete: false,
      updateResult: null,
      config: {},
      showVersionModal: false,
      pendingVersionInstall: null,
      versionsMap: {},
      selectedVersions: {},
    }
    // Provide a minimal pywebview mock on window
    window.pywebview = {
      api: {
        run_update: vi.fn(),
        launch_app: vi.fn(),
        install_versioned_package: vi.fn(),
      },
    }
  })

  function mountPanel() {
    return mount(ActionPanel, {
      global: {
        provide: { store },
      },
    })
  }

  // -------------------------------------------------------------------
  // Button disabled cases
  // -------------------------------------------------------------------

  it('test_install_button_disabled_when_no_packages', () => {
    store.packages = []
    store.selectedVersions = {}

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-install-version')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('test_install_button_disabled_when_selected_equals_installed', () => {
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: '1.0.0', status: 'up_to_date' },
    ]
    store.selectedVersions = { 'pkg-a': '1.0.0' }

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-install-version')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('test_install_button_disabled_when_isUpdating', () => {
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' },
    ]
    store.selectedVersions = { 'pkg-a': '0.9.0' }
    store.isUpdating = true

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-install-version')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('test_install_button_disabled_when_selected_version_is_null', () => {
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: null, status: 'up_to_date' },
    ]
    store.selectedVersions = { 'pkg-a': null }

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-install-version')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  // -------------------------------------------------------------------
  // Button enabled cases
  // -------------------------------------------------------------------

  it('test_install_button_enabled_when_version_differs', () => {
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' },
    ]
    store.selectedVersions = { 'pkg-a': '0.9.0' }

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-install-version')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('test_install_button_enabled_for_first_eligible_package', () => {
    // First package matches installed; second is different - button should enable
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: '1.0.0', status: 'up_to_date' },
      { name: 'pkg-b', installed: '2.0.0', available: '2.0.0', status: 'up_to_date' },
    ]
    store.selectedVersions = { 'pkg-a': '1.0.0', 'pkg-b': '1.5.0' }

    const wrapper = mountPanel()
    const btn = wrapper.find('.btn-install-version')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  // -------------------------------------------------------------------
  // Click behaviour
  // -------------------------------------------------------------------

  it('test_clicking_button_sets_pendingVersionInstall', async () => {
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' },
    ]
    store.selectedVersions = { 'pkg-a': '0.9.0' }

    const wrapper = mountPanel()
    await wrapper.find('.btn-install-version').trigger('click')

    expect(store.pendingVersionInstall).toEqual({
      packageName: 'pkg-a',
      version: '0.9.0',
    })
  })

  it('test_clicking_button_shows_modal', async () => {
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' },
    ]
    store.selectedVersions = { 'pkg-a': '0.9.0' }

    const wrapper = mountPanel()
    await wrapper.find('.btn-install-version').trigger('click')

    expect(store.showVersionModal).toBe(true)
  })

  it('test_clicking_button_picks_first_eligible_package', async () => {
    // pkg-a matches (no change), pkg-b differs -> button should target pkg-b
    store.packages = [
      { name: 'pkg-a', installed: '1.0.0', available: '1.0.0', status: 'up_to_date' },
      { name: 'pkg-b', installed: '2.0.0', available: '2.0.0', status: 'up_to_date' },
    ]
    store.selectedVersions = { 'pkg-a': '1.0.0', 'pkg-b': '1.5.0' }

    const wrapper = mountPanel()
    await wrapper.find('.btn-install-version').trigger('click')

    expect(store.pendingVersionInstall).toEqual({
      packageName: 'pkg-b',
      version: '1.5.0',
    })
  })
})
