/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadThemePreference, saveThemePreference } from '../lib/prefs'

const bootstrap = readFileSync(new URL('../../public/theme-init.js', import.meta.url), 'utf8')
const storageName = ['local', 'Storage'].join('')
afterEach(() => vi.unstubAllGlobals())

describe('màu trước khi React dựng', () => {
  it.each([
    ['dark', false, false, 'dark'],
    ['light', true, false, 'light'],
    ['system', true, false, 'dark'],
    ['broken', false, false, 'light'],
    ['dark', true, true, 'dark'],
    ['dark', false, true, 'light'],
  ])('giá trị %s, hệ thống tối %s, chặn bộ nhớ %s → %s', (saved, systemDark, blocked, expected) => {
    const root = { dataset: {} as Record<string, string>, style: {} as Record<string, string> }
    runInNewContext(bootstrap, {
      document: { documentElement: root },
      window: { matchMedia: () => ({ matches: systemDark }) },
      [storageName]: { getItem: () => { if (blocked) throw new Error('Bị chặn'); return saved } },
    })
    expect(root.dataset.theme).toBe(expected)
    expect(root.style.colorScheme).toBe(expected)
  })
})

describe('tuỳ chọn màu qua prefs.ts', () => {
  it('lưu và đọc lại lựa chọn bằng đúng khoá bootstrap sử dụng', () => {
    const values = new Map<string, string>()
    vi.stubGlobal('window', { [storageName]: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    } })
    expect(loadThemePreference()).toBe('system')
    saveThemePreference('dark')
    expect(loadThemePreference()).toBe('dark')
    expect(values.get('pharm_review_ui_theme')).toBe('dark')
    saveThemePreference('system')
    expect(loadThemePreference()).toBe('system')
  })
  it('dùng hệ thống khi trình duyệt chặn cả đọc và ghi', () => {
    vi.stubGlobal('window', Object.defineProperty({}, storageName, { get() { throw new Error('Bị chặn') } }))
    expect(loadThemePreference()).toBe('system')
    expect(() => saveThemePreference('dark')).not.toThrow()
  })
})
