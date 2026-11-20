import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError } from '../api/client'
import type { AuthHooks, FetchLike } from '../api/client'
import { createApiClient } from '../api/index'
import { MockClient } from '../api/mock'
import { defaultAuthClient } from '../features/auth/authClient'
import { saveDemoMode } from '../lib/demoSession'

const errorResponse = (status = 401, ma = 'phien_het_han', message = 'Phiên hết hạn') =>
  new Response(JSON.stringify({ loi: { ma, thong_bao: message } }), { status })
const ok = () => new Response(JSON.stringify({ ok: true }))

function setup(fetcher: FetchLike) {
  let token: string | null = 'token-cu'
  const hooks: AuthHooks = {
    getAccessToken: vi.fn(async () => token),
    refreshSession: vi.fn(async () => { token = 'token-moi'; return {} }),
    onUnauthorized: vi.fn(() => { token = null }),
    onForbidden: vi.fn(),
  }
  return { client: new ApiClient('/api', fetcher, hooks), hooks }
}

afterEach(() => { saveDemoMode(false); vi.restoreAllMocks(); vi.useRealTimers(); vi.unstubAllEnvs() })

describe('token và gia hạn của API', () => {
  it('gắn token cho mọi điểm cuối, giữ thân POST và chỉ để token trong tiêu đề', async () => {
    const fetcher = vi.fn<FetchLike>(async () => ok())
    const { client } = setup(fetcher)
    await client.getHealth()
    await client.getMe()
    await client.getCases()
    await client.getCase('DEMO-02')
    await client.getRecord('DEMO-02', 'XN-1')
    await client.sendFeedback('DEMO-02', { nhan_dinh_id: 'nd-1', phan_hoi: 'dong_y' })
    await client.ask('DEMO-02', { cau_hoi: 'Kiểm tra', lich_su: [] })
    await client.startAi('DEMO-02', true)
    await client.getAi('DEMO-02')
    await client.getSource('DEMO-02', 'nguon-1')
    await client.getConversations()
    await client.clearConversation('DEMO-02')
    expect(fetcher).toHaveBeenCalledTimes(12)
    for (const [url, init] of fetcher.mock.calls) {
      expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer token-cu')
      expect(String(url)).not.toContain('token-cu')
      expect(String(init?.body)).not.toContain('token-cu')
    }
    expect(new Headers(fetcher.mock.calls[5][1]?.headers).get('Content-Type')).toBe('application/json')
  })

  it('401 gia hạn một lần, gửi lại đúng một lần với token mới và cùng thân yêu cầu', async () => {
    const fetcher = vi.fn<FetchLike>().mockResolvedValueOnce(errorResponse()).mockResolvedValueOnce(ok())
    const { client, hooks } = setup(fetcher)
    await client.ask('DEMO-02', { cau_hoi: 'Kiểm tra', lich_su: [] })
    expect(hooks.refreshSession).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer token-moi')
    expect(fetcher.mock.calls[1][1]?.body).toBe(fetcher.mock.calls[0][1]?.body)
    expect(hooks.onUnauthorized).not.toHaveBeenCalled()
  })

  it.each(['null', 'throw'])('gia hạn thất bại (%s) xoá phiên, giữ mã lỗi và bỏ tiêu đề sau đăng xuất', async (failure) => {
    const fetcher = vi.fn<FetchLike>().mockImplementation(async () => errorResponse())
    const { client, hooks } = setup(fetcher)
    hooks.refreshSession = vi.fn(async () => {
      if (failure === 'throw') throw new Error('Lỗi dịch vụ')
      return null
    })
    await expect(client.getCases()).rejects.toMatchObject({ ma: 'phien_het_han', status: 401 })
    expect(hooks.onUnauthorized).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledTimes(1)
    fetcher.mockResolvedValueOnce(ok())
    await client.getHealth()
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).has('Authorization')).toBe(false)
  })

  it('401 sau gửi lại kết thúc, không lặp vô hạn', async () => {
    const fetcher = vi.fn<FetchLike>(async () => errorResponse(401, 'chua_dang_nhap'))
    const { client, hooks } = setup(fetcher)
    await expect(client.getCases()).rejects.toMatchObject({ ma: 'chua_dang_nhap', status: 401 })
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(hooks.refreshSession).toHaveBeenCalledTimes(1)
    expect(hooks.onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('nhiều 401 đồng thời và phản hồi 401 đến muộn dùng cùng một lần gia hạn', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn<FetchLike>(async (_url, init) => {
      if (new Headers(init?.headers).get('Authorization') === 'Bearer token-moi') return ok()
      await new Promise((resolve) => setTimeout(resolve, String(_url).endsWith('/health') ? 100 : 0))
      return errorResponse()
    })
    const { client, hooks } = setup(fetcher)
    const refresh = hooks.refreshSession
    hooks.refreshSession = vi.fn(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
      return refresh()
    })
    const pending = Promise.all([client.getCases(), client.getMe(), client.getHealth()])
    await vi.runAllTimersAsync()
    await pending
    expect(hooks.refreshSession).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledTimes(6)
  })

  it('403 giữ mã và gọi onForbidden, không đăng xuất hoặc gia hạn', async () => {
    const { client, hooks } = setup(async () => errorResponse(403, 'khong_co_quyen', 'Không đủ quyền'))
    await expect(client.getMe()).rejects.toMatchObject({ ma: 'khong_co_quyen', status: 403 })
    expect(hooks.onForbidden).toHaveBeenCalledTimes(1)
    expect(hooks.onUnauthorized).not.toHaveBeenCalled()
    expect(hooks.refreshSession).not.toHaveBeenCalled()
  })

  it('không đưa token bị phản chiếu vào ApiError hoặc console', async () => {
    const spies = ['log', 'warn', 'error', 'info', 'debug'].map((method) =>
      vi.spyOn(console, method as 'log').mockImplementation(() => {}))
    const { client } = setup(async () => errorResponse(403, 'khong_co_quyen', 'Sai token-cu'))
    const error = await client.getCases().catch((value: unknown) => value)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).not.toContain('token-cu')
    expect((error as ApiError).thong_bao).not.toContain('token-cu')
    for (const spy of spies) expect(spy).not.toHaveBeenCalled()
    const network = setup(async () => { throw new Error('Lỗi token-cu') })
    await expect(network.client.getCases()).rejects.toMatchObject({ message: 'Không thể kết nối máy chủ: Lỗi [ẩn]' })
  })

  it('giữ AbortError và không gửi lại yêu cầu bị huỷ trong khi gia hạn', async () => {
    const controller = new AbortController()
    const fetcher = vi.fn<FetchLike>(async () => errorResponse())
    const { client, hooks } = setup(fetcher)
    hooks.refreshSession = vi.fn(async () => { controller.abort(); return {} })
    await expect(client.ask('DEMO-02', { cau_hoi: 'Kiểm tra', lich_su: [] }, { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(hooks.onUnauthorized).not.toHaveBeenCalled()
    const aborted = new DOMException('Đã huỷ', 'AbortError')
    const plain = new ApiClient('/api', async () => { throw aborted })
    await expect(plain.getCases()).rejects.toBe(aborted)
  })

  it('giữ tương thích không có auth và getAi 404 chua_chay', async () => {
    const fetcher = vi.fn<FetchLike>(async () => errorResponse(404, 'chua_chay'))
    expect(await new ApiClient('/api', fetcher).getAi('DEMO-02')).toBeNull()
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has('Authorization')).toBe(false)
  })

  it('máy khách mặc định nối Supabase, demo bỏ token và mock không cần xác thực', async () => {
    vi.stubEnv('DEV', true)
    const getToken = vi.spyOn(defaultAuthClient, 'getAccessToken').mockResolvedValue('token-thu')
    const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => ok())
    const client = await createApiClient(false)
    await client.getMe()
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer token-thu')
    saveDemoMode(true)
    await client.getCases()
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).has('Authorization')).toBe(false)
    expect(getToken).toHaveBeenCalledTimes(1)
    const mock = await createApiClient(true)
    expect(mock).toBeInstanceOf(MockClient)
    await mock.getMe()
    expect(getToken).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
