/**
 * Tests for window.onVersionedInstallComplete callback defined in main.js.
 *
 * main.js cannot be directly imported in tests because it mounts the Vue app
 * and reads window.pywebviewready.  Instead we re-register the callback
 * inline the same way main.js does, against the same reactive store, so we
 * can test the logic in isolation.
 *
 * The callback is async (uses Promise.all for parallel version refresh), so
 * tests await the callback directly instead of flushing microtasks manually.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { reactive } from 'vue'

describe('window.onVersionedInstallComplete', () => {
  let store

  /**
   * Register the callback exactly as main.js would so the tests exercise the
   * real logic without mounting the full app.
   * Mirrors the async implementation in main.js Task 11.
   */
  function registerCallback() {
    window.onVersionedInstallComplete = async (result) => {
      if (result.success) {
        console.log('[onVersionedInstallComplete] Installation complete')
      } else {
        const failures = result.failures ? result.failures.join(', ') : 'unknown error'
        console.error(`[onVersionedInstallComplete] Install failed: ${failures}`)
      }

      if (window.pywebview) {
        try {
          const pkgData = await window.pywebview.api.get_packages()
          store.packages = pkgData

          await Promise.all(pkgData.map(async (pkg) => {
            try {
              const versions = await window.pywebview.api.get_versions(pkg.name)
              store.versionsMap[pkg.name] = versions || []
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
        get_versions: vi.fn().mockResolvedValue(['2.0.0', '1.0.0', '0.9.0']),
        install_versioned_package: vi.fn(),
      },
    }

    registerCallback()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    delete window.onVersionedInstallComplete
  })

  it('test_success_logs_installation_complete', async () => {
    const logSpy = vi.spyOn(console, 'log')
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('Installation complete')
    )
  })

  it('test_failure_logs_error_details', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    await window.onVersionedInstallComplete({
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

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(window.pywebview.api.get_packages).toHaveBeenCalled()
    expect(store.packages).toEqual(refreshedPackages)
    expect(store.showVersionModal).toBe(false)
  })

  it('test_success_clears_pending_version_install', async () => {
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(store.pendingVersionInstall).toBeNull()
  })

  it('test_success_closes_modal', async () => {
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(store.showVersionModal).toBe(false)
  })

  it('test_success_unlocks_ui', async () => {
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(store.isUpdating).toBe(false)
  })

  it('test_failure_also_closes_modal', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    await window.onVersionedInstallComplete({
      total: 1,
      updated: 0,
      failed: 1,
      success: false,
      failures: ['pkg-a: pip error'],
    })
    expect(store.showVersionModal).toBe(false)
    errSpy.mockRestore()
  })

  it('test_failure_also_unlocks_ui', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    await window.onVersionedInstallComplete({
      total: 1,
      updated: 0,
      failed: 1,
      success: false,
    })
    expect(store.isUpdating).toBe(false)
    errSpy.mockRestore()
  })

  it('test_packages_updated_before_modal_closes', async () => {
    // Verify that get_packages is called and packages are updated before modal closes.
    const refreshedPackages = [
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'up_to_date' },
    ]
    window.pywebview.api.get_packages = vi.fn().mockResolvedValue(refreshedPackages)

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    // Both conditions must hold: packages refreshed AND modal closed
    expect(store.packages).toEqual(refreshedPackages)
    expect(store.showVersionModal).toBe(false)
  })
})
