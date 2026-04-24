/**
 * Tests for auto-refresh behavior after versioned installation completes.
 *
 * Covers:
 *   - onVersionedInstallComplete does NOT call get_packages() (would overwrite correct status)
 *   - onVersionedInstallComplete calls get_versions() for each package in store.packages
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
// Helper: register onVersionedInstallComplete exactly as main.js does.
// store.packages already has correct statuses from window.updatePackages (called
// by backend before this event fires). Do NOT call get_packages() here — it
// always returns up_to_date and would overwrite the correct status.
// ---------------------------------------------------------------------------
function registerCallback(store) {
  window.onVersionedInstallComplete = async (result) => {
    if (result.success) {
      console.log('[onVersionedInstallComplete] Installation complete')
    } else {
      const failures = result.failures ? result.failures.join(', ') : 'unknown error'
      console.error(`[onVersionedInstallComplete] Install failed: ${failures}`)
    }

    // store.packages already has correct statuses from window.updatePackages (called by
    // backend before this event fires). Do NOT call get_packages() here — it always
    // returns up_to_date and would overwrite the correct status.
    // Just refresh the version dropdown selections to match the newly installed versions.
    if (window.pywebview) {
      try {
        await Promise.all(store.packages.map(async (pkg) => {
          try {
            const versions = await window.pywebview.api.get_versions(pkg.name)
            store.versionsMap[pkg.name] = versions || []
            store.selectedVersions[pkg.name] = pkg.installed || (versions && versions[0]) || null
          } catch (err) {
            console.warn(`[onVersionedInstallComplete] Failed to load versions for ${pkg.name}:`, err)
            store.versionsMap[pkg.name] = []
          }
        }))
      } catch (err) {
        console.error('[onVersionedInstallComplete] Refresh failed:', err)
      }
    }

    store.pendingVersionInstall = null
    store.showVersionModal = false
    store.isUpdating = false
  }
}

// ---------------------------------------------------------------------------
// Suite 1: onVersionedInstallComplete refresh chain
// ---------------------------------------------------------------------------
describe('onVersionedInstallComplete - auto-refresh after install', () => {
  let store

  beforeEach(() => {
    store = reactive({
      packages: [
        { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
      ],
      isUpdating: true,
      showVersionModal: true,
      pendingVersionInstall: { packageName: 'pkg-a', version: '0.9.0', installedVersion: '1.0.0' },
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

  it('test_does_not_call_get_packages_on_completion', async () => {
    // get_packages always returns up_to_date and would overwrite the correct status
    // pushed by updatePackages. The callback must NOT call it.
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(window.pywebview.api.get_packages).not.toHaveBeenCalled()
  })

  it('test_store_packages_status_preserved_not_overwritten', async () => {
    // store.packages already has correct status from updatePackages (update_available
    // after downgrade). Must remain unchanged after callback.
    const statusBefore = store.packages[0].status
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
    expect(store.packages[0].status).toBe(statusBefore)
  })

  it('test_calls_get_versions_for_each_package', async () => {
    store.packages = [
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
      { name: 'pkg-b', installed: '3.0.0', available: '3.0.0', status: 'up_to_date' },
    ]
    store.versionsMap['pkg-b'] = ['3.0.0']
    store.selectedVersions['pkg-b'] = '3.0.0'

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(window.pywebview.api.get_versions).toHaveBeenCalledWith('pkg-a')
    expect(window.pywebview.api.get_versions).toHaveBeenCalledWith('pkg-b')
    expect(window.pywebview.api.get_versions).toHaveBeenCalledTimes(2)
  })

  it('test_selected_version_updated_to_newly_installed_version', async () => {
    // store.packages has installed='0.9.0' (downgrade). selectedVersions should follow.
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })
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

  it('test_ui_unlocked_even_if_get_versions_fails_for_one_package', async () => {
    window.pywebview.api.get_versions.mockRejectedValue(new Error('versions unavailable'))
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(store.isUpdating).toBe(true)
    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(store.isUpdating).toBe(false)
    warnSpy.mockRestore()
  })

  it('test_versions_map_emptied_if_get_versions_fails_for_package', async () => {
    window.pywebview.api.get_versions.mockRejectedValue(new Error('versions unavailable'))
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    await window.onVersionedInstallComplete({ total: 1, updated: 1, failed: 0, success: true })

    expect(store.versionsMap['pkg-a']).toEqual([])
    warnSpy.mockRestore()
  })

  it('test_multiple_packages_refreshed_in_parallel', async () => {
    store.packages = [
      { name: 'pkg-a', installed: '0.9.0', available: '2.0.0', status: 'update_available' },
      { name: 'pkg-b', installed: '1.5.0', available: '1.5.0', status: 'up_to_date' },
      { name: 'pkg-c', installed: '3.1.0', available: '3.2.0', status: 'update_available' },
    ]
    store.versionsMap['pkg-b'] = ['1.5.0']
    store.versionsMap['pkg-c'] = ['3.2.0', '3.1.0']
    store.selectedVersions['pkg-b'] = '1.5.0'
    store.selectedVersions['pkg-c'] = '3.1.0'

    const callOrder = []
    window.pywebview.api.get_versions.mockImplementation((name) => {
      callOrder.push(name)
      return Promise.resolve(['1.0.0'])
    })

    await window.onVersionedInstallComplete({ total: 3, updated: 3, failed: 0, success: true })

    expect(callOrder).toContain('pkg-a')
    expect(callOrder).toContain('pkg-b')
    expect(callOrder).toContain('pkg-c')
    expect(window.pywebview.api.get_versions).toHaveBeenCalledTimes(3)
  })

  it('test_install_failure_still_unlocks_ui', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await window.onVersionedInstallComplete({
      total: 1, updated: 0, failed: 1, success: false, failures: ['pkg-a: uninstall failed'],
    })

    expect(store.isUpdating).toBe(false)
    errSpy.mockRestore()
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

    let rows = wrapper.findAll('.table-row')
    rows.forEach((row) => {
      expect(row.classes()).toContain('row-refreshing')
    })

    store.isUpdating = false
    await wrapper.vm.$nextTick()

    rows = wrapper.findAll('.table-row')
    rows.forEach((row) => {
      expect(row.classes()).not.toContain('row-refreshing')
    })
  })
})

// ---------------------------------------------------------------------------
// Suite 3: getEffectiveStatus override — version_specified display logic
// ---------------------------------------------------------------------------
describe('PackageTable.vue - getEffectiveStatus version_specified display', () => {
  let store

  function makeStore(overrides = {}) {
    return reactive({
      packages: [],
      isUpdating: false,
      versionsMap: {},
      selectedVersions: {},
      showVersionModal: false,
      pendingVersionInstall: null,
      ...overrides,
    })
  }

  it('test_shows_version_specified_when_up_to_date_but_different_version_selected', async () => {
    store = makeStore({
      packages: [{ name: 'pkg-a', installed: '2.0.0', available: '2.0.0', status: 'up_to_date' }],
      versionsMap: { 'pkg-a': ['2.0.0', '1.0.0'] },
      selectedVersions: { 'pkg-a': '1.0.0' },
    })

    const wrapper = mount(PackageTable, { global: { provide: { store } } })
    const statusCell = wrapper.find('.table-row .col-status')
    expect(statusCell.text()).toContain('Version specified')
    expect(statusCell.classes()).toContain('status-specified')
  })

  it('test_shows_up_to_date_when_selected_matches_installed', async () => {
    store = makeStore({
      packages: [{ name: 'pkg-a', installed: '2.0.0', available: '2.0.0', status: 'up_to_date' }],
      versionsMap: { 'pkg-a': ['2.0.0', '1.0.0'] },
      selectedVersions: { 'pkg-a': '2.0.0' },
    })

    const wrapper = mount(PackageTable, { global: { provide: { store } } })
    const statusCell = wrapper.find('.table-row .col-status')
    expect(statusCell.text()).toContain('Up to date')
    expect(statusCell.classes()).toContain('status-ok')
  })

  it('test_row_has_specified_class_when_version_specified', async () => {
    store = makeStore({
      packages: [{ name: 'pkg-a', installed: '2.0.0', available: '2.0.0', status: 'up_to_date' }],
      versionsMap: { 'pkg-a': ['2.0.0', '1.0.0'] },
      selectedVersions: { 'pkg-a': '1.0.0' },
    })

    const wrapper = mount(PackageTable, { global: { provide: { store } } })
    const row = wrapper.find('.table-row')
    expect(row.classes()).toContain('row-specified')
  })

  it('test_update_available_status_not_overridden_by_effective_status', async () => {
    store = makeStore({
      packages: [{ name: 'pkg-a', installed: '1.0.0', available: '2.0.0', status: 'update_available' }],
      versionsMap: { 'pkg-a': ['2.0.0', '1.0.0'] },
      selectedVersions: { 'pkg-a': '2.0.0' },
    })

    const wrapper = mount(PackageTable, { global: { provide: { store } } })
    const statusCell = wrapper.find('.table-row .col-status')
    expect(statusCell.text()).toContain('Update')
    expect(statusCell.classes()).toContain('status-update')
  })
})
