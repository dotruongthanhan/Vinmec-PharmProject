import { describe, expect, it } from 'vitest'
import { evaluateProtectedRoute, resolveLoginRedirect } from '../lib/routeGuard.ts'

describe('bảo vệ tuyến /app/*', () => {
  it('trả về loading khi phiên đang kiểm tra', () => {
    expect(
      evaluateProtectedRoute({
        isAuthenticated: false,
        isDemoMode: false,
        isLoading: true,
        currentPath: '/app/y-lenh/DEMO-02',
      }),
    ).toEqual({ action: 'loading' })
  })

  it('chuyển hướng về /dang-nhap và giữ đường dẫn quay lại khi chưa đăng nhập và không ở demo', () => {
    expect(
      evaluateProtectedRoute({
        isAuthenticated: false,
        isDemoMode: false,
        isLoading: false,
        currentPath: '/app/y-lenh/DEMO-02?tab=xet_nghiem',
      }),
    ).toEqual({
      action: 'redirect',
      to: '/dang-nhap',
      returnTo: '/app/y-lenh/DEMO-02?tab=xet_nghiem',
    })
  })

  it('cho phép truy cập khi đã đăng nhập hoặc đang ở chế độ demo', () => {
    expect(
      evaluateProtectedRoute({
        isAuthenticated: true,
        isDemoMode: false,
        isLoading: false,
        currentPath: '/app',
      }),
    ).toEqual({ action: 'allow' })

    expect(
      evaluateProtectedRoute({
        isAuthenticated: false,
        isDemoMode: true,
        isLoading: false,
        currentPath: '/app/y-lenh/DEMO-02',
      }),
    ).toEqual({ action: 'allow' })
  })

  it('chỉ chấp nhận đường dẫn quay lại an toàn bắt đầu bằng /app', () => {
    expect(resolveLoginRedirect({ from: '/app/y-lenh/DEMO-02' })).toBe('/app/y-lenh/DEMO-02')
    expect(resolveLoginRedirect({ from: '//malicious.example' })).toBe('/app')
    expect(resolveLoginRedirect({ from: '/' })).toBe('/app')
    expect(resolveLoginRedirect(null)).toBe('/app')
  })
})
