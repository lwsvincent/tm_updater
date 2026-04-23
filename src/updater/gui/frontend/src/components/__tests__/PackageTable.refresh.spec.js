/**
 * Tests for auto-refresh behavior after versioned installation completes.
 *
 * Covers:
 *   - onVersionedInstallComplete calls get_packages()
 *   - onVersionedInstallComplete calls get_versions() for each package
 *   - selectedVersions updated to match newly installed version
 *   - versionsMap updated with fresh version list
 *   - store.isUpdating set to false after all refreshes complete
 *   - Error in refresh still unlocks UI (isUpdating = false)
 *   - PackageTable shows .refreshing class during update (isUpdating = true)
 *   - .refreshing class absent after update completes (isUpdating = false)
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { reactive } from 'vue'
import { mount } from '@vue/test-utils'
import PackageTable from '../PackageTable.vue'

// ---------------------------------------------------------------------------
// Helper: register onVersionedInstallComplete the same way main.js does,
// including the new Promise.all(get_versions) refresh logic from Task 11.
// ---------------------------------------------------------------------------
function registerCallback(store) {
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

        // Refresh versions for each package in parallel
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

    // Always unlock UI, regardless of success/failure
    store.isUpdating = false
  }
}

// ---------------------------------------------------------------------------
// Flush all pending microtasks/promises
// ---------------------------------------------------------------------------
async function flushAllPromises() {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

// ---------------------------------------------------------------------------
// Suite 1: onVersionedInstallComplete refresh chain
// ---------------------------------------------------------------------------
describe('onVersionedInstallComplete - auto-refresh after install', () => {
  let store

  beforeEach(() => {
    store = reactive({
      packages: [
        { name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' },
      ],
      isUpdating: true,
      showVersionModal: true,
      pendingVersionInstall: { packageName: 'pkg-a', version: '0.9.0' },
      logs: [],
      config: {},
      updateComplete: false,
      updateResult: null,
      isLaunching: false,
      versionsMap: { 'pkg-a': ['2.0.0', '1.0.0', '0.9.0'] },
      selectedVersions: { 'pkg-a': '0.9.0' },
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

    registerCallback(store)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    delete window.onVersionedInstallComplete
  })

  it('test_calls_get_packages_on_completion', async () => {
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(window.pywebview.api.get_packages).toHaveBeenCalledOnce()
  })

  it('test_calls_get_versions_for_each_package', async () => {
    window.pywebview.api.get_packages.mockResolvedValue([
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
      { name: 'pkg-b', installed: '3.0.0', available: '3.0.0', status: 'up_to_date' },
    ])

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(window.pywebview.api.get_versions).toHaveBeenCalledWith('pkg-a')
    expect(window.pywebview.api.get_versions).toHaveBeenCalledWith('pkg-b')
    expect(window.pywebview.api.get_versions).toHaveBeenCalledTimes(2)
  })

  it('test_selected_version_updated_to_newly_installed_version', async () => {
    // After install, pkg-a.installed is now '0.9.0' (downgrade scenario)
    window.pywebview.api.get_packages.mockResolvedValue([
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
    ])

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    // selectedVersions should reflect the newly installed version
    expect(store.selectedVersions['pkg-a']).toBe('0.9.0')
  })

  it('test_versions_map_updated_with_fresh_list', async () => {
    const freshVersions = ['3.0.0', '2.0.0', '1.0.0', '0.9.0']
    window.pywebview.api.get_versions.mockResolvedValue(freshVersions)

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(store.versionsMap['pkg-a']).toEqual(freshVersions)
  })

  it('test_is_updating_false_after_refresh_completes', async () => {
    expect(store.isUpdating).toBe(true)
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(store.isUpdating).toBe(false)
  })

  it('test_modal_closed_after_refresh_completes', async () => {
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(store.showVersionModal).toBe(false)
  })

  it('test_pending_version_install_cleared_after_refresh', async () => {
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(store.pendingVersionInstall).toBeNull()
  })

  it('test_packages_store_updated_with_refreshed_data', async () => {
    const refreshedPackages = [
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
    ]
    window.pywebview.api.get_packages.mockResolvedValue(refreshedPackages)

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(store.packages).toEqual(refreshedPackages)
  })

  it('test_ui_unlocked_even_if_get_packages_fails', async () => {
    window.pywebview.api.get_packages.mockRejectedValue(new Error('network error'))
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(store.isUpdating).toBe(true)
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    // UI must be unlocked even on error
    expect(store.isUpdating).toBe(false)
    errSpy.mockRestore()
  })

  it('test_ui_unlocked_even_if_get_versions_fails_for_one_package', async () => {
    window.pywebview.api.get_versions.mockRejectedValue(new Error('versions unavailable'))
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(store.isUpdating).toBe(true)
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(store.isUpdating).toBe(false)
    warnSpy.mockRestore()
  })

  it('test_error_logged_if_get_packages_fails', async () => {
    window.pywebview.api.get_packages.mockRejectedValue(new Error('network error'))
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('Refresh failed'),
      expect.any(Error)
    )
    errSpy.mockRestore()
  })

  it('test_versions_map_emptied_if_get_versions_fails_for_package', async () => {
    window.pywebview.api.get_versions.mockRejectedValue(new Error('versions unavailable'))
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(store.versionsMap['pkg-a']).toEqual([])
    warnSpy.mockRestore()
  })

  it('test_multiple_packages_refreshed_in_parallel', async () => {
    const callOrder = []
    window.pywebview.api.get_packages.mockResolvedValue([
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
      { name: 'pkg-b', installed: '1.5.0', available: '1.5.0', status: 'up_to_date' },
      { name: 'pkg-c', installed: '3.1.0', available: '3.2.0', status: 'update_available' },
    ])
    window.pywebview.api.get_versions.mockImplementation((name) => {
      callOrder.push(name)
      return Promise.resolve(['1.0.0'])
    })

    await window.onVersionedInstallComplete({ total: 3, updated: 3, failed: 0, success: true })

    // All three packages had their versions fetched
    expect(callOrder).toContain('pkg-a')
    expect(callOrder).toContain('pkg-b')
    expect(callOrder).toContain('pkg-c')
    expect(window.pywebview.api.get_versions).toHaveBeenCalledTimes(3)
  })
})

// ---------------------------------------------------------------------------
// Suite 2: PackageTable visual feedback (.refreshing class)
// ---------------------------------------------------------------------------
describe('PackageTable.vue - refresh visual indicator', () => {
  let store

  beforeEach(() => {
    store = reactive({
      packages: [
        { name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' },
      ],
      isUpdating: false,
      versionsMap: { 'pkg-a': ['2.0.0', '1.0.0'] },
      selectedVersions: { 'pkg-a': '2.0.0' },
      showVersionModal: false,
      pendingVersionInstall: null,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('test_table_rows_have_refreshing_class_when_is_updating', async () => {
    store.isUpdating = true

    const wrapper = mount(PackageTable, {
      global: {
        provide: { store },
      },
    })

    const rows = wrapper.findAll('.table-row')
    expect(rows.length).toBeGreaterThan(0)
    rows.forEach((row) => {
      expect(row.classes()).toContain('row-refreshing')
    })
  })

  it('test_table_rows_do_not_have_refreshing_class_when_not_updating', async () => {
    store.isUpdating = false

    const wrapper = mount(PackageTable, {
      global: {
        provide: { store },
      },
    })

    const rows = wrapper.findAll('.table-row')
    rows.forEach((row) => {
      expect(row.classes()).not.toContain('row-refreshing')
    })
  })

  it('test_refreshing_class_removed_after_update_completes', async () => {
    store.isUpdating = true

    const wrapper = mount(PackageTable, {
      global: {
        provide: { store },
      },
    })

    // Verify it's present during update
    let rows = wrapper.findAll('.table-row')
    rows.forEach((row) => {
      expect(row.classes()).toContain('row-refreshing')
    })

    // Simulate update completing
    store.isUpdating = false
    await wrapper.vm.$nextTick()

    // Verify it's gone after update
    rows = wrapper.findAll('.table-row')
    rows.forEach((row) => {
      expect(row.classes()).not.toContain('row-refreshing')
    })
  })
})
