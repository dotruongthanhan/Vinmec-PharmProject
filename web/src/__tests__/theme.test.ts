import { describe, expect, it } from 'vitest'
import { resolveTheme, parseThemePreference } from '../lib/theme'

describe('quyết định chế độ màu', () => {
  it.each([
    ['light', true, 'light'], ['light', false, 'light'],
    ['dark', true, 'dark'], ['dark', false, 'dark'],
    ['system', true, 'dark'], ['system', false, 'light'],
    ['broken', true, 'dark'], [null, false, 'light'],
    ['', true, 'dark'], [undefined, false, 'light'],
  ])('lựa chọn %s, hệ thống tối %s → %s', (preference, systemDark, expected) => {
    expect(resolveTheme(preference, systemDark)).toBe(expected)
  })

  it('coi giá trị lưu hỏng là Theo hệ thống', () => {
    expect(parseThemePreference('garbage')).toBe('system')
    expect(parseThemePreference(null)).toBe('system')
    expect(parseThemePreference('dark')).toBe('dark')
  })
})
