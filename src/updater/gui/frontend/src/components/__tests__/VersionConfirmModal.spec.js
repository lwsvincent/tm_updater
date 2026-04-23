import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import VersionConfirmModal from '../VersionConfirmModal.vue'

describe('VersionConfirmModal.vue', () => {
  let store

  beforeEach(() => {
    store = {
      showVersionModal: false,
      pendingVersionInstall: null,
    }
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

  it('test_confirm_button_triggers_install', async () => {
    store.showVersionModal = true
    store.pendingVersionInstall = { packageName: 'test-pkg', version: '2.0.0' }

    // Mock console.log to verify the call
    const logSpy = vi.spyOn(console, 'log')

    const wrapper = mount(VersionConfirmModal, {
      global: {
        provide: {
          store: store,
        },
      },
    })

    await wrapper.find('.btn-confirm').trigger('click')

    // Task 10 will replace this with actual API call
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('Will install: test-pkg@2.0.0')
    )
    expect(store.showVersionModal).toBe(false)

    logSpy.mockRestore()
  })
})
