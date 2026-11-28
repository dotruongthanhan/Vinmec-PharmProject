import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../api/client'
import type { AuthHooks, FetchLike } from '../api/client'

afterEach(() => { vi.useRealTimers() })

describe('huỷ yêu cầu và báo đăng xuất cho backend', () => {
  it('abortAll huỷ cả yêu cầu đọc và hỏi đáp, vẫn cho phép yêu cầu mới', async () => {
    const signals: AbortSignal[] = []
    const fetcher: FetchLike = async (_url, init) => {
      const signal = init!.signal!
      signals.push(signal)
      return new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(signal.reason), { once: true })
      })
    }
    const client = new ApiClient('/api', fetcher)
    const reads = client.getCases().catch((error: unknown) => error)
    const asks = client.ask('DEMO-02', { cau_hoi: 'Kiểm tra', lich_su: [] }).catch((error: unknown) => error)
    await Promise.resolve()
    client.abortAll()
    expect(signals).toHaveLength(2)
    expect(signals.every((signal) => signal.aborted)).toBe(true)
    expect(await reads).toMatchObject({ name: 'AbortError' })
    expect(await asks).toMatchObject({ name: 'AbortError' })
    const next = client.getCases().catch((error: unknown) => error)
    await Promise.resolve()
    expect(signals[2].aborted).toBe(false)
    client.abortAll()
    await next
  })

  it('huỷ cả yêu cầu còn đang đợi lấy token, không gửi yêu cầu sau đó', async () => {
    let resolveToken!: (token: string) => void
    const fetcher = vi.fn<FetchLike>()
    const auth: AuthHooks = {
      getAccessToken: () => new Promise((resolve) => { resolveToken = resolve }),
      refreshSession: async () => null,
      onUnauthorized: vi.fn(),
    }
    const client = new ApiClient('/api', fetcher, auth)
    const pending = client.getCases().catch((error: unknown) => error)
    client.abortAll()
    resolveToken('token-gia-lap')
    expect(await pending).toMatchObject({ name: 'AbortError' })
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('không trả dữ liệu đến muộn sau khi huỷ trong lúc đọc thân phản hồi', async () => {
    let resolveBody!: (body: string) => void
    const response = new Response()
    response.text = () => new Promise((resolve) => { resolveBody = resolve })
    const client = new ApiClient('/api', async () => response)
    const pending = client.getCases().catch((error: unknown) => error)
    for (let i = 0; i < 5; i += 1) await Promise.resolve()
    client.abortAll()
    resolveBody('{}')
    expect(await pending).toMatchObject({ name: 'AbortError' })
  })

  it('gửi đúng một POST không thân với token đã giữ, không gia hạn hoặc phát 401', async () => {
    const fetcher = vi.fn<FetchLike>(async () => new Response('{}', { status: 401 }))
    const auth: AuthHooks = {
      getAccessToken: vi.fn(async () => 'token-khac'),
      refreshSession: vi.fn(async () => null),
      onUnauthorized: vi.fn(),
    }
    const client = new ApiClient('/api', fetcher, auth)
    await client.signOut('token-gia-lap')
    expect(fetcher).toHaveBeenCalledTimes(1)
    const [path, init] = fetcher.mock.calls[0]
    expect(path).toBe('/api/dang-xuat')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeUndefined()
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer token-gia-lap')
    expect(auth.getAccessToken).not.toHaveBeenCalled()
    expect(auth.refreshSession).not.toHaveBeenCalled()
    expect(auth.onUnauthorized).not.toHaveBeenCalled()
  })

  it('bỏ qua lỗi mạng và kết thúc sau ba giây kể cả fetch treo', async () => {
    vi.useFakeTimers()
    let signal: AbortSignal | null | undefined
    const client = new ApiClient('/api', async (_url, init) => {
      signal = init?.signal
      return new Promise(() => {})
    })
    let done = false
    const pending = client.signOut('token-gia-lap').then(() => { done = true })
    await vi.advanceTimersByTimeAsync(2999)
    expect(done).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    await pending
    expect(signal?.aborted).toBe(true)
    expect(done).toBe(true)
    await new ApiClient('/api', async () => { throw new Error('Lỗi giả lập') }).signOut('token-gia-lap')
    expect(vi.getTimerCount()).toBe(0)
  })
})
