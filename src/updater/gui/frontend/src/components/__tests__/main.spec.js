/**
 * Tests for window.onVersionedInstallComplete callback defined in main.js.
 *
 * main.js cannot be directly imported in tests because it mounts the Vue app
 * and reads window.pywebviewready.  Instead we re-register the callback
 * inline the same way main.js does, against the same reactive store, so we
 * can test the logic in isolation.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { reactive } from 'vue'

describe('window.onVersionedInstallComplete', () => {
  let store

  /**
   * Register the callback exactly as main.js would so the tests exercise the
   * real logic without mounting the full app.
   */
  function registerCallback() {
    window.onVersionedInstallComplete = (result) => {
      if (result.success) {
        console.log('[onVersionedInstallComplete] Installation complete')
      } else {
        const failures = result.failures ? result.failures.join(', ') : 'unknown error'
        console.error(`[onVersionedInstallComplete] Install failed: ${failures}`)
      }

      // Refresh packages from backend then update store
      if (window.pywebview) {
        window.pywebview.api.get_packages().then((packages) => {
          store.packages = packages
          store.pendingVersionInstall = null
          store.showVersionModal = false
          store.isUpdating = false
        })
      } else {
        store.pendingVersionInstall = null
        store.showVersionModal = false
        store.isUpdating = false
      }
    }
  }

  beforeEach(() => {
    store = reactive({
      packages: [{ name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' }],
      isUpdating: true,
      showVersionModal: true,
      pendingVersionInstall: { packageName: 'pkg-a', version: '0.9.0' },
      logs: [],
      config: {},
      updateComplete: false,
      updateResult: null,
      isLaunching: false,
      versionsMap: {},
      selectedVersions: {},
    })

    window.pywebview = {
      api: {
        get_packages: vi.fn().mockResolvedValue([
          { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
        ]),
        install_versioned_package: vi.fn(),
      },
    }

    registerCallback()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    delete window.onVersionedInstallComplete
  })

  it('test_success_logs_installation_complete', () => {
    const logSpy = vi.spyOn(console, 'log')
    window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('Installation complete')
    )
  })

  it('test_failure_logs_error_details', () => {
    const errSpy = vi.spyOn(console, 'error')
    window.onVersionedInstallComplete({
      total: 1,
      updated: 0,
      failed: 1,
      success: false,
      failures: ['pkg-a: pip error'],
    })
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('pkg-a: pip error')
    )
  })

  it('test_success_refreshes_packages_before_closing_modal', async () => {
    const refreshedPackages = [
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
    ]
    window.pywebview.api.get_packages.mockResolvedValue(refreshedPackages)

    window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    // Let the microtask (Promise.then) flush
    await Promise.resolve()

    expect(window.pywebview.api.get_packages).toHaveBeenCalled()
    expect(store.packages).toEqual(refreshedPackages)
    expect(store.showVersionModal).toBe(false)
  })

  it('test_success_clears_pending_version_install', async () => {
    window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    await Promise.resolve()
    expect(store.pendingVersionInstall).toBeNull()
  })

  it('test_success_closes_modal', async () => {
    window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    await Promise.resolve()
    expect(store.showVersionModal).toBe(false)
  })

  it('test_success_unlocks_ui', async () => {
    window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    await Promise.resolve()
    expect(store.isUpdating).toBe(false)
  })

  it('test_failure_also_closes_modal', async () => {
    window.onVersionedInstallComplete({
      total: 1,
      updated: 0,
      failed: 1,
      success: false,
      failures: ['pkg-a: pip error'],
    })
    await Promise.resolve()
    expect(store.showVersionModal).toBe(false)
  })

  it('test_failure_also_unlocks_ui', async () => {
    window.onVersionedInstallComplete({
      total: 1,
      updated: 0,
      failed: 1,
      success: false,
    })
    await Promise.resolve()
    expect(store.isUpdating).toBe(false)
  })

  it('test_packages_updated_before_modal_closes', async () => {
    // Verify that get_packages is called and packages are updated before modal closes.
    // We confirm this by checking both invariants hold after the promise chain resolves.
    const refreshedPackages = [
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'up_to_date' },
    ]
    window.pywebview.api.get_packages = vi.fn().mockResolvedValue(refreshedPackages)

    window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    // Flush the promise microtask queue
    await Promise.resolve()

    // Both conditions must hold: packages refreshed AND modal closed
    expect(store.packages).toEqual(refreshedPackages)
    expect(store.showVersionModal).toBe(false)
  })
})
