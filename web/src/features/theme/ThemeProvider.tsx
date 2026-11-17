import { useCallback, useLayoutEffect, useMemo, useState, useSyncExternalStore } from 'react'
import type { ReactNode } from 'react'
import { loadThemePreference, saveThemePreference } from '@/lib/prefs'
import { resolveTheme } from '@/lib/theme'
import type { ThemePreference } from '@/lib/theme'
import { ThemeContext } from './useTheme'

const SYSTEM_QUERY = '(prefers-color-scheme: dark)'

function getSystemDark(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(SYSTEM_QUERY).matches : false
}

function subscribeToSystemTheme(onChange: () => void): () => void {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return () => {}
  const media = window.matchMedia(SYSTEM_QUERY)
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}

/** Đồng bộ màu trước khi vẽ, giữ nguyên cây trạng thái khi đổi lựa chọn. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setStoredPreference] = useState<ThemePreference>(loadThemePreference)
  const systemDark = useSyncExternalStore(subscribeToSystemTheme, getSystemDark, () => false)
  const theme = resolveTheme(preference, systemDark)
  const setPreference = useCallback((next: ThemePreference) => {
    saveThemePreference(next)
    setStoredPreference(next)
  }, [])

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    const meta = document.querySelector('meta[name="theme-color"]')
    meta?.setAttribute('content', getComputedStyle(document.documentElement).getPropertyValue('--color-canvas').trim())
  }, [theme])

  const value = useMemo(() => ({ preference, theme, setPreference }), [preference, theme, setPreference])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
