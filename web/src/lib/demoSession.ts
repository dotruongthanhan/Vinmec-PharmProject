const DEMO_SESSION_KEY = 'pharm_review_demo'

/** Chỉ khôi phục cờ demo hợp lệ khi chưa cấu hình xác thực. */
export function shouldRestoreDemoMode(flag: string | null, isConfigured: boolean): boolean {
  return !isConfigured && flag === '1'
}

export function loadDemoMode(isConfigured: boolean): boolean {
  try {
    return shouldRestoreDemoMode(window.sessionStorage.getItem(DEMO_SESSION_KEY), isConfigured)
  } catch {
    return false
  }
}

/** Chỉ lưu một cờ trong phiên, không lưu thông tin xác thực. */
export function saveDemoMode(enabled: boolean): void {
  try {
    if (enabled) {
      window.sessionStorage.setItem(DEMO_SESSION_KEY, '1')
    } else {
      window.sessionStorage.removeItem(DEMO_SESSION_KEY)
    }
  } catch {
    // Vẫn cho dùng demo khi trình duyệt chặn bộ nhớ.
  }
}
