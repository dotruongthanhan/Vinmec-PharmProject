import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../features/auth/AuthProvider'
import type { AuthContextValue } from '../features/auth/useAuth'
import type { AuthClient, AuthSession, AuthStateListener } from '../features/auth/authClient'
import { notifyAuthEvent } from '../features/auth/authEvents'
import type { MeResponse } from '../api/types'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../features/auth/useAuth'
import { LoginPage } from '../features/auth/LoginPage'

const backend = vi.hoisted(() => ({ abortAll: vi.fn(), signOut: vi.fn(async (_token: string) => {}) }))
vi.mock('../api/index', async (original) => ({ ...await original<typeof import('../api/index')>(), apiClient: backend }))
vi.mock('../features/theme/ThemeControl', () => ({ ThemeControl: () => null }))

// Bộ chạy hook tối thiểu cho môi trường Node; API và vòng đời đều được điều khiển trong test.
const hooks = vi.hoisted(() => {
  type Slot = { value?: unknown; deps?: unknown[]; cleanup?: () => void; setter?: (value: unknown) => void }
  type Runner = { slots: Slot[]; cursor: number; effects: (() => void)[] }
  let active: Runner
  const same = (a?: unknown[], b?: unknown[]) => !!a && !!b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]))
  const slot = () => active.slots[active.cursor++] ?? (active.slots[active.cursor - 1] = {})
  const memoize = (fn: () => unknown, deps?: unknown[]) => {
    const cell = slot()
    if (!same(cell.deps, deps)) { cell.value = fn(); cell.deps = deps }
    return cell.value
  }
  return {
    useState: (initial: unknown) => {
      const cell = slot()
      if (!cell.setter) {
        cell.value = typeof initial === 'function' ? initial() : initial
        cell.setter = (value: unknown) => { cell.value = typeof value === 'function' ? value(cell.value) : value }
      }
      return [cell.value, cell.setter]
    },
    useRef: (initial: unknown) => {
      const cell = slot()
      return cell.value ?? (cell.value = { current: initial })
    },
    useMemo: memoize,
    useCallback: (fn: unknown, deps?: unknown[]) => memoize(() => fn, deps),
    useEffect: (effect: () => (() => void) | void, deps?: unknown[]) => {
      const cell = slot()
      if (!same(cell.deps, deps)) {
        cell.deps = deps
        active.effects.push(() => { cell.cleanup?.(); cell.cleanup = effect() || undefined })
      }
    },
    create: () => {
      const runner: Runner = { slots: [], cursor: 0, effects: [] }
      return {
        render: <T,>(fn: () => T): T => {
          active = runner
          runner.cursor = 0
          const result = fn()
          for (const effect of runner.effects.splice(0)) effect()
          return result
        },
        unmount: () => { for (const cell of runner.slots) cell.cleanup?.(); runner.slots = [] },
      }
    },
  }
})
vi.mock('react', async (original) => ({ ...await original<typeof import('react')>(), ...hooks }))

const session: AuthSession = { user: { id: 'tai-khoan-a', email: 'a@example.invalid' }, vaiTro: 'duoc_si_ls', phienId: 'phien-a' }
const me: MeResponse = { id: 'tai-khoan-a', email: 'a@example.invalid', vai_tro: 'admin', phien_id: 'phien-a' }
const tick = async () => { for (let i = 0; i < 15; i += 1) await Promise.resolve() }
const cleanups: (() => void)[] = []
afterEach(() => {
  for (const cleanup of cleanups.splice(0)) cleanup()
  vi.unstubAllEnvs(); vi.restoreAllMocks(); vi.clearAllMocks(); vi.useRealTimers(); vi.unstubAllGlobals()
  backend.signOut.mockImplementation(async () => {})
})

function mount(initial: AuthSession | null, getMe = vi.fn(async () => me)) {
  const runner = hooks.create()
  cleanups.push(runner.unmount)
  let current = initial
  let listener: AuthStateListener | undefined
  const client: AuthClient = {
    isConfigured: true,
    getSession: vi.fn(async () => current),
    getAccessToken: vi.fn(async () => current ? 'token-thu' : null),
    refreshSession: vi.fn(async () => current),
    onAuthStateChange: (next) => { listener = next; return () => { listener = undefined } },
    signInWithPassword: vi.fn(async () => { current = session; listener?.(session); return { session, error: null } }),
    signOut: vi.fn(async () => { current = null; listener?.(null) }),
  }
  const render = () => runner.render(() => AuthProvider({ client, getMe, children: null }).props.value as AuthContextValue)
  render()
  return { render, client, getMe, event: (next: AuthSession | null, event?: string) => { current = next; listener?.(next, event) } }
}

describe('đăng xuất thống nhất', () => {
  it.each(['local', 'global'] as const)('xoá giao diện ngay, thu hồi một lần trước Supabase scope=%s', async (scope) => {
    let release!: () => void
    backend.signOut.mockReturnValue(new Promise<void>((resolve) => { release = resolve }))
    const app = mount(session)
    await tick()
    const pending = app.render().signOut({ scope })
    expect(app.render()).toMatchObject({ session: null, signOutReason: 'nguoi_dung' })
    expect(backend.abortAll).toHaveBeenCalledTimes(1)
    expect(await app.render().getAccessToken()).toBeNull()
    void app.render().signOut({ scope })
    await tick()
    expect(backend.signOut).toHaveBeenCalledExactlyOnceWith('token-thu')
    expect(app.client.signOut).not.toHaveBeenCalled()
    release()
    await pending
    expect(app.client.signOut).toHaveBeenCalledExactlyOnceWith({ scope })
    expect(app.render().signOutReason).toBe('nguoi_dung')
  })

  it('lỗi backend không ngăn Supabase đăng xuất local', async () => {
    backend.signOut.mockRejectedValue(new Error('lỗi giả lập'))
    const app = mount(session)
    await tick()
    await app.render().signOut()
    expect(app.client.signOut).toHaveBeenCalledExactlyOnceWith({ scope: 'local' })
    expect(app.render().isAuthenticated).toBe(false)
  })

  it('backend treo chỉ trì hoãn Supabase tối đa ba giây', async () => {
    vi.useFakeTimers()
    backend.signOut.mockReturnValue(new Promise(() => {}))
    const app = mount(session)
    await tick()
    const pending = app.render().signOut()
    expect(app.render().isAuthenticated).toBe(false)
    await vi.advanceTimersByTimeAsync(2_999)
    expect(app.client.signOut).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    await pending
    expect(app.client.signOut).toHaveBeenCalledExactlyOnceWith({ scope: 'local' })
  })

  it('lấy token treo vẫn chuyển sang Supabase sau ba giây', async () => {
    vi.useFakeTimers()
    const app = mount(session)
    await tick()
    vi.mocked(app.client.getAccessToken).mockReturnValue(new Promise(() => {}))
    const pending = app.render().signOut()
    await vi.advanceTimersByTimeAsync(3_000)
    await pending
    expect(backend.signOut).not.toHaveBeenCalled()
    expect(app.client.signOut).toHaveBeenCalledTimes(1)
  })

  it('401 xoá phiên và đăng xuất Supabase mà không gọi backend', async () => {
    const app = mount(session)
    await tick()
    await notifyAuthEvent('unauthorized')
    expect(backend.signOut).not.toHaveBeenCalled()
    expect(app.client.signOut).toHaveBeenCalledExactlyOnceWith({ scope: 'local' })
    expect(app.render()).toMatchObject({ session: null, signOutReason: '401' })
  })

  it('SIGNED_OUT từ tab khác huỷ yêu cầu, xoá phiên và giữ lý do riêng', async () => {
    const app = mount(session)
    await tick()
    app.event(null, 'SIGNED_OUT')
    await tick()
    expect(backend.abortAll).toHaveBeenCalledTimes(1)
    expect(backend.signOut).not.toHaveBeenCalled()
    expect(app.client.signOut).not.toHaveBeenCalled()
    expect(app.render()).toMatchObject({ session: null, signOutReason: 'da_dang_xuat_noi_khac' })
  })

  it('gia hạn hoặc lấy token về muộn sau đăng xuất không khôi phục phiên', async () => {
    const app = mount(session)
    await tick()
    let refreshed!: (next: AuthSession | null) => void
    let token!: (next: string | null) => void
    vi.mocked(app.client.refreshSession).mockReturnValue(new Promise((resolve) => { refreshed = resolve }))
    vi.mocked(app.client.getAccessToken).mockReturnValueOnce(new Promise((resolve) => { token = resolve }))
    const pendingRefresh = app.render().refreshSession()
    const pendingToken = app.render().getAccessToken()
    await app.render().signOut({ reason: '401' })
    refreshed(session)
    token('token-cu')
    expect(await pendingRefresh).toBeNull()
    expect(await pendingToken).toBeNull()
    expect(app.render().session).toBeNull()
  })

  it('lỗi SDK vẫn giữ trạng thái giao diện đã đăng xuất', async () => {
    const app = mount(session)
    await tick()
    vi.mocked(app.client.signOut).mockRejectedValue(new Error('dịch vụ lỗi'))
    await expect(app.render().signOut()).resolves.toBeUndefined()
    expect(app.render()).toMatchObject({ session: null, signOutReason: 'nguoi_dung' })
  })

  it('TOKEN_REFRESHED không đặt lại hạn nhàn rỗi của phiên', async () => {
    vi.useFakeTimers()
    const app = mount(session)
    await tick()
    app.render()
    await vi.advanceTimersByTimeAsync(1_200_000)
    app.event(session, 'TOKEN_REFRESHED')
    await tick()
    app.render()
    await vi.advanceTimersByTimeAsync(600_000)
    expect(app.render()).toMatchObject({ session: null, signOutReason: 'khong_hoat_dong' })
  })

  it('chỉ phiên thật bật hạn giờ; đăng xuất dọn hẹn giờ', async () => {
    vi.useFakeTimers()
    const app = mount(session)
    await tick()
    app.render()
    await vi.advanceTimersByTimeAsync(1_800_000)
    expect(app.render()).toMatchObject({ session: null, signOutReason: 'khong_hoat_dong' })
    await tick()
    expect(backend.signOut).toHaveBeenCalledTimes(1)
    app.render()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('demo không bật hạn giờ', async () => {
    vi.useFakeTimers()
    vi.stubEnv('VITE_ENABLE_DEMO', '1')
    const app = mount(null)
    await tick()
    app.render().enterDemoMode()
    expect(app.render().isDemoMode).toBe(true)
    await vi.advanceTimersByTimeAsync(43_200_001)
    expect(app.render().isDemoMode).toBe(true)
    expect(backend.signOut).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('vào demo sau khi đăng xuất rồi vẫn thoát demo được', async () => {
    vi.stubEnv('VITE_ENABLE_DEMO', '1')
    const app = mount(session)
    await tick()
    await app.render().signOut()
    app.render().enterDemoMode()
    expect(app.render().isDemoMode).toBe(true)
    await app.render().signOut()
    expect(app.render().isDemoMode).toBe(false)
  })

  it('SIGNED_OUT của lần đăng xuất đang hoàn tất không đẩy người dùng khỏi demo mới mở', async () => {
    vi.stubEnv('VITE_ENABLE_DEMO', '1')
    let release!: () => void
    backend.signOut.mockReturnValue(new Promise<void>((resolve) => { release = resolve }))
    const app = mount(session)
    await tick()
    vi.mocked(app.client.signOut).mockImplementation(async () => { app.event(null, 'SIGNED_OUT') })
    const pending = app.render().signOut()
    await tick()
    app.render().enterDemoMode()
    expect(app.render().isDemoMode).toBe(true)
    release()
    await pending
    expect(app.render()).toMatchObject({ session: null, isDemoMode: true, signOutReason: null })
    expect(backend.signOut).toHaveBeenCalledTimes(1)
  })

  it('demo rồi đóng demo không làm đăng nhập mới vượt qua lần đăng xuất còn chờ', async () => {
    vi.stubEnv('VITE_ENABLE_DEMO', '1')
    let releaseBackend!: () => void
    let releaseSdk!: () => void
    backend.signOut.mockReturnValue(new Promise<void>((resolve) => { releaseBackend = resolve }))
    const app = mount(session)
    await tick()
    vi.mocked(app.client.signOut).mockImplementation(async () => {
      await new Promise<void>((resolve) => { releaseSdk = resolve })
      app.event(null, 'SIGNED_OUT')
    })
    const firstLogout = app.render().signOut()
    await tick()
    app.render().enterDemoMode()
    const closeDemo = app.render().signOut()
    const newLogin = app.render().signIn('b@example.invalid', 'gia-lap')
    await tick()
    expect(app.client.signInWithPassword).not.toHaveBeenCalled()
    expect(backend.signOut).toHaveBeenCalledTimes(1)
    releaseBackend()
    await tick()
    expect(app.client.signInWithPassword).not.toHaveBeenCalled()
    releaseSdk()
    await Promise.all([firstLogout, closeDemo, newLogin])
    expect(app.client.signInWithPassword).toHaveBeenCalledTimes(1)
    expect(backend.signOut).toHaveBeenCalledTimes(1)
    expect(app.client.signOut).toHaveBeenCalledTimes(1)
    expect(app.render()).toMatchObject({ isDemoMode: false, isAuthenticated: true, signOutReason: null })
  })
})

describe('thông báo lý do đăng xuất', () => {
  it.each([
    ['het_han_phien', 'Phiên đã hết hạn. Vui lòng đăng nhập lại.'],
    ['khong_hoat_dong', 'Bạn đã bị đăng xuất vì không hoạt động.'],
    ['da_dang_xuat_noi_khac', 'Bạn đã đăng xuất ở một thẻ hoặc thiết bị khác.'],
  ])('hiện thông báo cho %s', async (reason, message) => {
    const app = mount(null)
    await tick()
    const html = renderToStaticMarkup(
      <AuthContext.Provider value={app.render()}>
        <MemoryRouter initialEntries={[{ pathname: '/dang-nhap', state: { reason } }]}><LoginPage /></MemoryRouter>
      </AuthContext.Provider>,
    )
    expect(html).toContain(message)
  })

  it('đăng xuất chủ động không hiện thông báo hết hạn hoặc tab khác', async () => {
    const app = mount(null)
    await tick()
    const html = renderToStaticMarkup(
      <AuthContext.Provider value={app.render()}>
        <MemoryRouter initialEntries={[{ pathname: '/dang-nhap', state: { reason: 'nguoi_dung' } }]}><LoginPage /></MemoryRouter>
      </AuthContext.Provider>,
    )
    expect(html).not.toContain('Phiên đã hết hạn')
    expect(html).not.toContain('Bạn đã bị đăng xuất')
    expect(html).not.toContain('Bạn đã đăng xuất ở một thẻ')
  })
})
