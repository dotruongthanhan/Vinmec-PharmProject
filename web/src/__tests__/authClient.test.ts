import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createSupabaseAuthClient, mapSupabaseSession } from '../features/auth/authClient'

const sdk = vi.hoisted(() => ({
  getSession: vi.fn(), refreshSession: vi.fn(), signInWithPassword: vi.fn(),
  signOut: vi.fn(), onAuthStateChange: vi.fn(), createClient: vi.fn(),
}))
vi.mock('@supabase/supabase-js', () => ({ createClient: sdk.createClient }))

const token = `header.${btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify({ session_id: 'phien-thu', ghi_chu: 'Đã thử' })))).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')}.signature`
const rawSession = { access_token: token, user: { id: 'id-thu', email: 'thu@example.invalid', app_metadata: { role: 'duoc_si_ls' } } }

beforeEach(() => {
  vi.resetAllMocks()
  sdk.createClient.mockReturnValue({ auth: sdk })
  sdk.getSession.mockResolvedValue({ data: { session: rawSession }, error: null })
  sdk.refreshSession.mockResolvedValue({ data: { session: rawSession }, error: null })
  sdk.signOut.mockResolvedValue({ error: null })
})
afterEach(() => { vi.useRealTimers() })

describe('phiên Supabase', () => {
  it('chỉ tin app_metadata.role và đọc mã phiên JWT UTF-8', () => {
    expect(mapSupabaseSession(rawSession)).toMatchObject({ vaiTro: 'duoc_si_ls', phienId: 'phien-thu' })
    const attacker = { ...rawSession, user: { ...rawSession.user, app_metadata: {}, user_metadata: { role: 'admin' } } }
    expect(mapSupabaseSession(attacker)?.vaiTro).toBeNull()
    expect(mapSupabaseSession({ ...rawSession, user: { ...rawSession.user, app_metadata: { role: 'superuser' } } })?.vaiTro).toBeNull()
    expect(mapSupabaseSession({ ...rawSession, user: { ...rawSession.user, app_metadata: { role: 'admin' } } })?.vaiTro).toBe('admin')
  })

  it.each(['', 'hong', 'a.@@@.c', 'a.bnVsbA.c', 'a.e30.c', 'a.eyJzZXNzaW9uX2lkIjoxfQ.c'])('chịu được token hỏng hoặc thiếu session_id: %s', (access_token) => {
    expect(mapSupabaseSession({ ...rawSession, access_token })?.phienId).toBeNull()
  })

  it('lấy token qua getSession và bật lưu phiên, tự gia hạn trong SDK', async () => {
    const client = createSupabaseAuthClient('/supabase', 'public-placeholder')
    expect(await client.getAccessToken()).toBe(token)
    expect(sdk.getSession).toHaveBeenCalledTimes(1)
    expect(sdk.createClient).toHaveBeenCalledWith('/supabase', 'public-placeholder', {
      auth: { persistSession: true, autoRefreshToken: true },
    })
  })

  it('gia hạn đồng thời chờ chung một Promise; lần sau có thể gia hạn tiếp', async () => {
    vi.useFakeTimers()
    sdk.refreshSession.mockImplementation(async () => {
      await new Promise((resolve) => setTimeout(resolve, 100))
      return { data: { session: rawSession }, error: null }
    })
    const client = createSupabaseAuthClient('/supabase', 'public-placeholder')
    const first = client.refreshSession()
    expect(client.refreshSession()).toBe(first)
    await vi.runAllTimersAsync()
    expect(await first).toMatchObject({ phienId: 'phien-thu' })
    expect(sdk.refreshSession).toHaveBeenCalledTimes(1)
    const second = client.refreshSession()
    await vi.runAllTimersAsync()
    await second
    expect(sdk.refreshSession).toHaveBeenCalledTimes(2)
  })

  it('gia hạn thất bại trả null, đăng xuất chặn token kể cả SDK trả lỗi', async () => {
    const client = createSupabaseAuthClient('/supabase', 'public-placeholder')
    sdk.refreshSession.mockRejectedValue(new Error('Lỗi dịch vụ'))
    expect(await client.refreshSession()).toBeNull()
    sdk.signOut.mockRejectedValue(new Error('Không kết nối'))
    await expect(client.signOut()).rejects.toThrow('Không kết nối')
    expect(await client.getAccessToken()).toBeNull()
    expect(await client.getSession()).toBeNull()
    expect(await client.refreshSession()).toBeNull()
  })

  it('đăng xuất giữa lúc gia hạn không khôi phục token; đăng nhập mới hoạt động', async () => {
    let resolve!: (result: unknown) => void
    sdk.refreshSession.mockReturnValue(new Promise((done) => { resolve = done }))
    const client = createSupabaseAuthClient('/supabase', 'public-placeholder')
    const pending = client.refreshSession()
    await client.signOut()
    resolve({ data: { session: rawSession }, error: null })
    expect(await pending).toBeNull()
    sdk.signInWithPassword.mockResolvedValue({ data: { session: rawSession }, error: null })
    await client.signInWithPassword('thu@example.invalid', 'mat-khau-gia')
    expect(await client.getAccessToken()).toBe(token)
  })

  it('không phản chiếu lỗi đăng nhập có chứa token', async () => {
    sdk.signInWithPassword.mockResolvedValue({ data: {}, error: { message: token } })
    const client = createSupabaseAuthClient('/supabase', 'public-placeholder')
    expect((await client.signInWithPassword('thu@example.invalid', 'gia')).error).not.toContain(token)
  })
})
