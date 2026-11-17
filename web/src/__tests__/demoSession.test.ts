import { describe, expect, it } from 'vitest'
import { shouldRestoreDemoMode } from '../lib/demoSession'
import { evaluateProtectedRoute } from '../lib/routeGuard'

describe('khôi phục phiên demo', () => {
  it('cho phép mở thẳng chi tiết sau khi tải lại với đúng cờ demo', () => {
    expect(evaluateProtectedRoute({
      isAuthenticated: false,
      isDemoMode: shouldRestoreDemoMode('1', false),
      isLoading: false,
      currentPath: '/app/y-lenh/DEMO-02',
    })).toEqual({ action: 'allow' })
  })

  it('không bật demo từ cờ hỏng, cờ đã xoá hay khi đã cấu hình xác thực', () => {
    for (const flag of [null, '', 'true', '0', 'session-token']) {
      expect(shouldRestoreDemoMode(flag, false)).toBe(false)
    }
    expect(shouldRestoreDemoMode('1', true)).toBe(false)
  })
})
