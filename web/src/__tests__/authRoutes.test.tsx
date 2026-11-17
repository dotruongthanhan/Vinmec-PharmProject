import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../features/auth/useAuth'
import type { AuthContextValue } from '../features/auth/useAuth'
import { LoginPage } from '../features/auth/LoginPage'
import { ProtectedRoute } from '../features/auth/ProtectedRoute'
import { evaluateProtectedRoute, resolveLoginRedirect } from '../lib/routeGuard'
import { isDemoEnabled, loadDemoMode, saveDemoMode } from '../lib/demoSession'

vi.mock('../features/theme/ThemeControl', () => ({ ThemeControl: () => null }))

const context: AuthContextValue = {
  session: null, isAuthenticated: false, isDemoMode: false, isConfigured: false,
  isLoading: false, userEmail: null, vaiTro: null, phienId: null, isForbidden: false,
  verificationError: null, getAccessToken: async () => null, refreshSession: async () => null,
  verifyRole: async () => {}, signIn: async () => null, enterDemoMode: () => {}, signOut: async () => {},
}

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals() })

describe('bảo vệ vai trò và chế độ demo', () => {
  it('thiếu quyền bị chặn, vai trò hợp lệ cho phép, phiên đang tải giữ tuyến chi tiết', () => {
    const input = { isAuthenticated: true, isDemoMode: false, isLoading: false, currentPath: '/app/y-lenh/DEMO-02' }
    expect(evaluateProtectedRoute({ ...input, vaiTro: null })).toEqual({ action: 'forbidden' })
    for (const vaiTro of ['duoc_si_ls', 'admin'] as const) {
      expect(evaluateProtectedRoute({ ...input, vaiTro })).toEqual({ action: 'allow' })
    }
    expect(evaluateProtectedRoute({ ...input, isLoading: true, vaiTro: null })).toEqual({ action: 'loading' })
    expect(evaluateProtectedRoute({ ...input, isAuthenticated: false, vaiTro: null })).toEqual({
      action: 'redirect', to: '/dang-nhap', returnTo: input.currentPath,
    })
    expect(resolveLoginRedirect({ from: '/app/y-lenh/DEMO-02?tab=thuoc' })).toBe('/app/y-lenh/DEMO-02?tab=thuoc')
    expect(resolveLoginRedirect({ from: '//ngoai.invalid' })).toBe('/app')
  })

  it('tài khoản không quyền thấy hướng dẫn và cả hai nút, không có thông tin kỹ thuật', () => {
    const html = renderToStaticMarkup(
      <AuthContext.Provider value={{ ...context, isAuthenticated: true }}>
        <MemoryRouter initialEntries={['/app/y-lenh/DEMO-02']}><ProtectedRoute /></MemoryRouter>
      </AuthContext.Provider>,
    )
    expect(html).toContain('Tài khoản chưa được cấp quyền')
    expect(html).toContain('liên hệ quản trị')
    expect(html).toContain('Đăng xuất')
    expect(html).toContain('Thử lại')
    expect(html).not.toContain('JWT')
    expect(html).not.toContain('Supabase')
  })

  it.each([false, true])('production không cờ ẩn demo kể cả xác thực configured=%s', (isConfigured) => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_USE_MOCK', '')
    vi.stubEnv('VITE_ENABLE_DEMO', '')
    const html = renderToStaticMarkup(
      <AuthContext.Provider value={{ ...context, isConfigured }}><MemoryRouter><LoginPage /></MemoryRouter></AuthContext.Provider>,
    )
    expect(html).not.toContain('Vào bản demo')
    const storage = { getItem: vi.fn(() => '1'), setItem: vi.fn(), removeItem: vi.fn() }
    vi.stubGlobal('window', { [['session', 'Storage'].join('')]: storage })
    expect(loadDemoMode(isConfigured)).toBe(false)
    expect(storage.removeItem).toHaveBeenCalledWith('pharm_review_demo')
    saveDemoMode(true)
    expect(storage.setItem).not.toHaveBeenCalled()
  })

  it('chỉ bật demo khi DEV hoặc cờ cho phép, và hiển thị nút', () => {
    expect(isDemoEnabled({ DEV: false })).toBe(false)
    expect(isDemoEnabled({ DEV: true })).toBe(true)
    expect(isDemoEnabled({ DEV: false, VITE_USE_MOCK: '1' })).toBe(true)
    expect(isDemoEnabled({ DEV: false, VITE_ENABLE_DEMO: '1' })).toBe(true)
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_ENABLE_DEMO', '1')
    const html = renderToStaticMarkup(
      <AuthContext.Provider value={context}><MemoryRouter><LoginPage /></MemoryRouter></AuthContext.Provider>,
    )
    expect(html).toContain('Vào bản demo')
  })
})
