const DEMO_SESSION_KEY = 'pharm_review_demo'
let activeDemoMode = false

export interface DemoEnvironment {
  DEV?: boolean
  VITE_USE_MOCK?: string
  VITE_ENABLE_DEMO?: string
}

export function isDemoEnabled(env: DemoEnvironment = import.meta.env): boolean {
  return env.DEV === true || env.VITE_USE_MOCK === '1' || env.VITE_ENABLE_DEMO === '1'
}

export function isActiveDemoMode(): boolean {
  return isDemoEnabled() && activeDemoMode
}

/** Chỉ khôi phục cờ demo hợp lệ khi chưa cấu hình xác thực. */
export function shouldRestoreDemoMode(flag: string | null, isConfigured: boolean,
  env: DemoEnvironment = import.meta.env): boolean {
  return isDemoEnabled(env) && !isConfigured && flag === '1'
}

export function loadDemoMode(isConfigured: boolean): boolean {
  activeDemoMode = false
  try {
    if (!isDemoEnabled()) {
      activeDemoMode = false
      window.sessionStorage.removeItem(DEMO_SESSION_KEY)
      return false
    }
    activeDemoMode = shouldRestoreDemoMode(window.sessionStorage.getItem(DEMO_SESSION_KEY), isConfigured)
    return activeDemoMode
  } catch {
    return false
  }
}

/** Chỉ lưu một cờ trong phiên, không lưu thông tin xác thực. */
export function saveDemoMode(enabled: boolean): void {
  activeDemoMode = enabled && isDemoEnabled()
  try {
    if (enabled && isDemoEnabled()) {
      window.sessionStorage.setItem(DEMO_SESSION_KEY, '1')
    } else {
      window.sessionStorage.removeItem(DEMO_SESSION_KEY)
    }
  } catch {
    // Vẫn cho dùng demo khi trình duyệt chặn bộ nhớ.
  }
}
