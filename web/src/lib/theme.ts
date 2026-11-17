export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

/** Giá trị hỏng được hiểu là theo hệ thống. */
export function parseThemePreference(value: unknown): ThemePreference {
  return value === 'light' || value === 'dark' ? value : 'system'
}

/** Quyết định màu từ lựa chọn đã lưu và thiết lập hệ điều hành. */
export function resolveTheme(preference: unknown, systemDark: boolean): ResolvedTheme {
  const parsed = parseThemePreference(preference)
  return parsed === 'system' ? (systemDark ? 'dark' : 'light') : parsed
}
