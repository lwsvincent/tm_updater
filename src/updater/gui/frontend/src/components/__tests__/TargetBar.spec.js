import { describe, it, expect, beforeEach, vi } from 'vitest'
import { reactive } from 'vue'
import { mount } from '@vue/test-utils'
import TargetBar from '../TargetBar.vue'

describe('TargetBar.vue', () => {
  let store
  let reloadTarget

  beforeEach(() => {
    store = reactive({
      packages: [],
      logs: [],
      config: {},
      target: {
        project: 'D:\\Work\\ProjA',
        venv: 'D:\\Work\\ProjA\\venv',
        source: '\\\\pnt52\\packages',
        config: 'D:\\Work\\ProjA',
        config_origin: 'project',
        error: '',
      },
    })
    reloadTarget = vi.fn().mockResolvedValue({})
    window.pywebview = {
      api: {
        set_target: vi.fn(),
        choose_target_folder: vi.fn(),
      },
    }
  })

  function mountBar() {
    return mount(TargetBar, { global: { provide: { store, reloadTarget } } })
  }

  it('test_shows_resolved_project_and_venv', () => {
    const wrapper = mountBar()
    expect(wrapper.text()).toContain('D:\\Work\\ProjA')
    expect(wrapper.text()).toContain('venv:')
    expect(wrapper.find('.target-error').exists()).toBe(false)
  })

  it('test_apply_switches_target_and_reloads', async () => {
    window.pywebview.api.set_target.mockResolvedValue({
      error: null,
      target: {
        project: 'D:\\Work\\ProjB',
        venv: 'D:\\Work\\ProjB\\.venv',
        source: '\\\\pnt52\\packages',
        config: 'D:\\Work\\ProjB',
        config_origin: 'project',
        error: '',
      },
    })
    const wrapper = mountBar()
    const input = wrapper.get('input.target-input')
    await input.setValue('D:\\Work\\ProjB')
    await wrapper.get('button.btn-small').trigger('click')

    expect(window.pywebview.api.set_target).toHaveBeenCalledWith('D:\\Work\\ProjB')
    expect(store.target.project).toBe('D:\\Work\\ProjB')
    expect(reloadTarget).toHaveBeenCalled()
  })

  it('test_apply_keeps_old_target_and_shows_error_on_bad_path', async () => {
    window.pywebview.api.set_target.mockResolvedValue({
      error: '--project path not found: D:\\nope',
      target: store.target,
    })
    const wrapper = mountBar()
    await wrapper.get('input.target-input').setValue('D:\\nope')
    await wrapper.get('button.btn-small').trigger('click')

    expect(store.target.project).toBe('D:\\Work\\ProjA')
    expect(wrapper.get('.target-error').text()).toContain('not found')
    expect(reloadTarget).not.toHaveBeenCalled()
  })

  it('test_browse_cancelling_changes_nothing', async () => {
    window.pywebview.api.choose_target_folder.mockResolvedValue({ cancelled: true })
    const wrapper = mountBar()
    await wrapper.get('.btn-browse').trigger('click')

    expect(window.pywebview.api.choose_target_folder).toHaveBeenCalled()
    expect(store.target.project).toBe('D:\\Work\\ProjA')
    expect(reloadTarget).not.toHaveBeenCalled()
  })

  it('test_browse_selecting_folder_switches_target', async () => {
    window.pywebview.api.choose_target_folder.mockResolvedValue({
      error: null,
      target: {
        project: 'D:\\Work\\ProjC',
        venv: 'D:\\Work\\ProjC\\venv',
        source: '\\\\pnt52\\packages',
        config: 'D:\\Work\\ProjC',
        config_origin: 'builtin',
        error: '',
      },
    })
    const wrapper = mountBar()
    await wrapper.get('.btn-browse').trigger('click')

    expect(store.target.project).toBe('D:\\Work\\ProjC')
    expect(reloadTarget).toHaveBeenCalled()
  })

  it('test_toml_parse_error_is_surfaced_with_encoding', () => {
    store.target = {
      project: 'D:\\Work\\ProjE',
      venv: 'D:\\Work\\ProjE\\venv',
      source: '\\\\pnt52\\packages',
      config: 'D:\\Work\\ProjE',
      config_origin: 'project',
      error: '',
      config_error: 'updater.toml 無法解析，已改用內建預設值：Invalid statement',
      encoding: 'cp950',
    }
    const wrapper = mountBar()
    expect(wrapper.get('.target-error.warn').text()).toContain('無法解析')
    expect(wrapper.get('.target-error.warn').text()).toContain('cp950')
  })

  it('test_missing_venv_shows_backend_error_message', () => {
    store.target = {
      project: 'D:\\Work\\ProjD',
      venv: '',
      source: '\\\\pnt52\\packages',
      config: 'D:\\Work\\ProjD',
      config_origin: 'project',
      error: '找不到 venv，請指定正確的專案資料夾',
    }
    const wrapper = mountBar()
    expect(wrapper.get('.target-error').text()).toContain('找不到 venv')
  })
})
