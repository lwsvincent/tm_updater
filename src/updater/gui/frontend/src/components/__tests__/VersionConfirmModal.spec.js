import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { reactive } from 'vue'
import { mount } from '@vue/test-utils'
import VersionConfirmModal from '../VersionConfirmModal.vue'

describe('VersionConfirmModal.vue', () => {
  let store

  beforeEach(() => {
    store = reactive({
      showVersionModal: false,
      pendingVersionInstall: null,
      isUpdating: false,
      selectedVersions: { 'test-pkg': '2.0.0' },
    })
    window.pywebview = {
      api: {
        install_versioned_package: vi.fn().mockResolvedValue({ success: true, error: null }),
      },
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('test_modal_hidden_by_default', () => {
    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })
    expect(wrapper.find('.modal-overlay').exists()).toBe(false)
  })

  it('test_modal_shows_when_flag_true', () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0', installedVersion: '1.0.0' }

    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })
    expect(wrapper.find('.modal-overlay').exists()).toBe(true)
  })

  it('test_modal_displays_package_name_installed_and_target_version', () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0', installedVersion: '1.0.0' }

    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })

    const text = wrapper.text()
    expect(text).toContain('test-pkg')
    expect(text).toContain('1.0.0')
    expect(text).toContain('2.0.0')
  })

  it('test_cancel_button_closes_modal', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0', installedVersion: '1.0.0' }

    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })

    await wrapper.find('.btn-cancel').trigger('click')

    expect(store.showVersionModal).toBe(false)
    expect(store.pendingVersionInstall).toBeNull()
  })

  it('test_cancel_resets_selected_version_to_installed', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0', installedVersion: '1.0.0' }
    store.selectedVersions['test-pkg'] = '2.0.0'

    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })

    await wrapper.find('.btn-cancel').trigger('click')

    expect(store.selectedVersions['test-pkg']).toBe('1.0.0')
  })

  it('test_confirm_button_calls_install_versioned_package_api', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0', installedVersion: '1.0.0' }

    const apiSpy = vi.spyOn(window.pywebview.api, 'install_versioned_package')

    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })

    await wrapper.find('.btn-confirm').trigger('click')

    expect(apiSpy).toHaveBeenCalledWith('test-pkg', '2.0.0')
  })

  it('test_confirm_button_locks_modal_during_install', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0', installedVersion: '1.0.0' }
    store.isUpdating = false

    window.pywebview.api.install_versioned_package = vi.fn(
      () => new Promise(() => {})
    )

    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })

    await wrapper.find('.btn-confirm').trigger('click')

    expect(store.isUpdating).toBe(true)
    expect(store.showVersionModal).toBe(true)
  })

  it('test_cancel_button_disabled_during_install', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0', installedVersion: '1.0.0' }
    store.isUpdating = true

    const wrapper = mount(VersionConfirmModal, {
      global: { provide: { store } },
    })

    const cancelBtn = wrapper.find('.btn-cancel')
    const confirmBtn = wrapper.find('.btn-confirm')

    expect(cancelBtn.attributes('disabled')).toBeDefined()
    expect(confirmBtn.attributes('disabled')).toBeDefined()
  })
})
