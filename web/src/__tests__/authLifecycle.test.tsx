import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../features/auth/AuthProvider'
import type { AuthContextValue } from '../features/auth/useAuth'
import type { AuthClient, AuthSession, AuthStateListener } from '../features/auth/authClient'
import { notifyAuthEvent } from '../features/auth/authEvents'
import { ApiError } from '../api/client'
import type { MeResponse, TraLoi } from '../api/types'
import { MockClient } from '../api/mock'
import { useChat } from '../state/useChat'

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
const reply: TraLoi = { trang_thai: 'ok', noi_dung: 'Trả lời giả lập', trich_dan: [], cong_cu_da_goi: [] }
const tick = async () => { for (let i = 0; i < 15; i += 1) await Promise.resolve() }
const cleanups: (() => void)[] = []
afterEach(() => { for (const cleanup of cleanups.splice(0)) cleanup(); vi.unstubAllEnvs(); vi.restoreAllMocks() })

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
  return { render, client, getMe, event: (next: AuthSession | null) => { current = next; listener?.(next) } }
}

describe('vòng đời phiên và xác nhận quyền', () => {
  it('khôi phục phiên giữ trạng thái tải cho tới /me, tin quyền máy chủ và chỉ xác nhận một lần', async () => {
    let done!: (value: MeResponse) => void
    const getMe = vi.fn(() => new Promise<MeResponse>((resolve) => { done = resolve }))
    const app = mount(session, getMe)
    await tick()
    expect(app.render().isLoading).toBe(true)
    done(me)
    await tick()
    expect(app.render()).toMatchObject({ isLoading: false, vaiTro: 'admin', phienId: 'phien-a' })
    app.event({ ...session, vaiTro: null })
    await tick()
    expect(app.render().vaiTro).toBe('admin')
    expect(getMe).toHaveBeenCalledTimes(1)
  })

  it('đăng nhập và sự kiện SIGNED_IN dùng chung xác nhận /me; unauthorized xoá phiên và token', async () => {
    const app = mount(null)
    await tick()
    await app.render().signIn('a@example.invalid', 'gia-lap')
    expect(app.getMe).toHaveBeenCalledTimes(1)
    expect(app.render().isAuthenticated).toBe(true)
    await notifyAuthEvent('unauthorized')
    expect(app.render()).toMatchObject({ session: null, isAuthenticated: false, vaiTro: null, phienId: null })
    expect(await app.render().getAccessToken()).toBeNull()
    expect(app.client.signOut).toHaveBeenCalledTimes(1)
  })

  it('403 giữ phiên; Thử lại gọi /me và nhận quyền mới', async () => {
    const getMe = vi.fn<() => Promise<MeResponse>>().mockRejectedValueOnce(new ApiError('khong_co_quyen', 'Không đủ quyền', 403)).mockResolvedValueOnce(me)
    const app = mount({ ...session, vaiTro: null }, getMe)
    await tick()
    expect(app.render()).toMatchObject({ isAuthenticated: true, isForbidden: true, verificationError: null })
    expect(app.client.signOut).not.toHaveBeenCalled()
    await app.render().verifyRole()
    expect(app.render()).toMatchObject({ isForbidden: false, vaiTro: 'admin' })
    expect(getMe).toHaveBeenCalledTimes(2)
    await notifyAuthEvent('forbidden')
    expect(app.render().isForbidden).toBe(true)
    app.event(session)
    await tick()
    expect(app.render().isForbidden).toBe(true)
    expect(app.client.signOut).not.toHaveBeenCalled()
  })

  it('xác nhận về muộn sau đăng xuất không khôi phục phiên', async () => {
    let done!: (value: MeResponse) => void
    const app = mount(session, vi.fn(() => new Promise<MeResponse>((resolve) => { done = resolve })))
    await tick()
    await app.render().signOut()
    done(me)
    await tick()
    expect(app.render().session).toBeNull()
  })

  it('production không cờ: gọi enterDemoMode trực tiếp cũng bị từ chối', async () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_USE_MOCK', '')
    vi.stubEnv('VITE_ENABLE_DEMO', '')
    const app = mount(null)
    await tick()
    app.render().enterDemoMode()
    expect(app.render().isDemoMode).toBe(false)
  })
})

describe('hội thoại khi rời phiên', () => {
  it('xoá bộ nhớ, huỷ yêu cầu đang chạy và không đưa lịch sử tài khoản A sang tài khoản B', async () => {
    const clientA = new MockClient({ delayMs: 0, askDelayMs: 0 })
    const getConversations = vi.fn(async () => ({ 'DEMO-02': [{ cau_hoi: 'Câu hỏi riêng của A', tra_loi: reply }] }))
    const clientWithHistory = Object.assign(clientA, { getConversations })
    const a = hooks.create()
    const renderA = () => a.render(() => useChat(clientWithHistory, 'DEMO-02'))
    renderA()
    await tick()
    expect(renderA().getMessages('DEMO-02')).toHaveLength(2)
    let requestSignal: AbortSignal | undefined
    let done!: (value: TraLoi) => void
    vi.spyOn(clientWithHistory, 'ask').mockImplementation((_id, _payload, options) => {
      requestSignal = options?.signal
      return new Promise((resolve) => { done = resolve })
    })
    const pending = renderA().sendQuestion('DEMO-02', 'Câu hỏi tiếp theo')
    a.unmount()
    expect(requestSignal?.aborted).toBe(true)
    done(reply)
    await pending
    const b = hooks.create()
    cleanups.push(b.unmount)
    const clientB = Object.assign(new MockClient({ delayMs: 0 }), { getConversations: vi.fn(async () => ({})) })
    const renderB = () => b.render(() => useChat(clientB, 'DEMO-02'))
    renderB()
    await tick()
    expect(renderB().getMessages('DEMO-02')).toEqual([])
    expect(renderB().askedCaseIds).toEqual([])
  })
})
