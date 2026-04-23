import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import VersionConfirmModal from '../VersionConfirmModal.vue'

describe('VersionConfirmModal.vue', () => {
  let store

  beforeEach(() => {
    store = {
      showVersionModal: false,
      pendingVersionInstall: null,
      isUpdating: false,
    }
    // Provide pywebview mock so the confirm handler can call the API
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
      global: {
        provide: {
          store: store,
        },
      },
    })

    expect(wrapper.find('.modal-overlay').exists()).toBe(false)
  })

  it('test_modal_shows_when_flag_true', () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0' }

    const wrapper = mount(VersionConfirmModal, {
      global: {
        provide: {
          store: store,
        },
      },
    })

    expect(wrapper.find('.modal-overlay').exists()).toBe(true)
  })

  it('test_modal_displays_version', () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0' }

    const wrapper = mount(VersionConfirmModal, {
      global: {
        provide: {
          store: store,
        },
      },
    })

    expect(wrapper.text()).toContain('2.0.0')
  })

  it('test_cancel_button_closes_modal', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0' }

    const wrapper = mount(VersionConfirmModal, {
      global: {
        provide: {
          store: store,
        },
      },
    })

    await wrapper.find('.btn-cancel').trigger('click')

    expect(store.showVersionModal).toBe(false)
    expect(store.pendingVersionInstall).toBeNull()
  })

  it('test_confirm_button_calls_install_versioned_package_api', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0' }

    const apiSpy = vi.spyOn(window.pywebview.api, 'install_versioned_package')

    const wrapper = mount(VersionConfirmModal, {
      global: {
        provide: {
          store: store,
        },
      },
    })

    await wrapper.find('.btn-confirm').trigger('click')

    expect(apiSpy).toHaveBeenCalledWith('test-pkg', '2.0.0')
  })

  it('test_confirm_button_locks_modal_during_install', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0' }
    store.isUpdating = false

    // Make the API call hang (never resolves) so we can inspect the locked state
    window.pywebview.api.install_versioned_package = vi.fn(
      () => new Promise(() => {}) // intentionally never resolves
    )

    const wrapper = mount(VersionConfirmModal, {
      global: {
        provide: {
          store: store,
        },
      },
    })

    await wrapper.find('.btn-confirm').trigger('click')

    // After click, store.isUpdating should be true (locked)
    expect(store.isUpdating).toBe(true)
    // Modal should still be visible during install
    expect(store.showVersionModal).toBe(true)
  })

  it('test_cancel_button_disabled_during_install', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0' }
    store.isUpdating = true

    const wrapper = mount(VersionConfirmModal, {
      global: {
        provide: {
          store: store,
        },
      },
    })

    const cancelBtn = wrapper.find('.btn-cancel')
    const confirmBtn = wrapper.find('.btn-confirm')

    expect(cancelBtn.attributes('disabled')).toBeDefined()
    expect(confirmBtn.attributes('disabled')).toBeDefined()
  })
})
