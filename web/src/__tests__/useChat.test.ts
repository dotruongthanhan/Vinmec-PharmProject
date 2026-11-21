import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client.ts'
import type { ReviewApiClient } from '../api/client.ts'
import { MockClient } from '../api/mock.ts'
import type { BuocAI, GuiCauHoi, TienTrinhHoiDap, TraLoi } from '../api/types.ts'
import {
  ASK_PROGRESS_POLL_INTERVAL_MS,
  formatAskErrorMessage,
  useChat,
} from '../state/useChat.ts'

// Bộ chạy hook tối thiểu cho môi trường Node (không phụ thuộc jsdom).
const hooks = vi.hoisted(() => {
  type Slot = {
    value?: unknown
    deps?: unknown[]
    cleanup?: () => void
    setter?: (value: unknown) => void
  }
  type Runner = { slots: Slot[]; cursor: number; effects: (() => void)[] }
  let active: Runner
  const same = (a?: unknown[], b?: unknown[]) =>
    !!a && !!b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]))
  const slot = () => active.slots[active.cursor++] ?? (active.slots[active.cursor - 1] = {})
  const memoize = (fn: () => unknown, deps?: unknown[]) => {
    const cell = slot()
    if (!same(cell.deps, deps)) {
      cell.value = fn()
      cell.deps = deps
    }
    return cell.value
  }
  return {
    useState: (initial: unknown) => {
      const cell = slot()
      if (!cell.setter) {
        cell.value = typeof initial === 'function' ? initial() : initial
        cell.setter = (value: unknown) => {
          cell.value = typeof value === 'function' ? value(cell.value) : value
        }
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
        active.effects.push(() => {
          cell.cleanup?.()
          cell.cleanup = effect() || undefined
        })
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
        unmount: () => {
          for (const cell of runner.slots) cell.cleanup?.()
          runner.slots = []
        },
      }
    },
  }
})

vi.mock('react', async (original) => ({
  ...(await original<typeof import('react')>()),
  ...hooks,
}))

const sampleReply: TraLoi = {
  trang_thai: 'ok',
  noi_dung: 'Trả lời giả lập',
  trich_dan: [],
  cong_cu_da_goi: ['du_lieu_ca'],
  thoi_gian_ms: 10,
}

const cleanups: (() => void)[] = []

afterEach(() => {
  for (const cleanup of cleanups.splice(0)) cleanup()
  vi.restoreAllMocks()
})

describe('useChat không gửi lich_su và vẫn giữ hiển thị lịch sử trên màn hình', () => {
  it('thân yêu cầu ask không có khoá lich_su cho cả ca bệnh và __global__', async () => {
    const sentPayloads: GuiCauHoi[] = []
    const client = new MockClient({ delayMs: 0, askDelayMs: 0 })
    vi.spyOn(client, 'ask').mockImplementation(async (_caId, payload) => {
      sentPayloads.push(payload)
      return sampleReply
    })

    const runner = hooks.create()
    cleanups.push(runner.unmount)
    let activeCase = 'DEMO-02'
    const render = () => runner.render(() => useChat(client, activeCase))

    await render().sendQuestion('DEMO-02', 'Câu hỏi 1')
    await render().sendQuestion('DEMO-02', 'Câu hỏi 2', 'nd-1')
    activeCase = '__global__'
    await render().sendQuestion('__global__', 'Câu hỏi chung')

    expect(sentPayloads).toHaveLength(3)
    for (const payload of sentPayloads) {
      expect('lich_su' in payload).toBe(false)
      expect(Object.keys(payload).sort()).toEqual(['cau_hoi', 'nhan_dinh_id'])
    }
    expect(sentPayloads[0]).toEqual({ cau_hoi: 'Câu hỏi 1', nhan_dinh_id: null })
    expect(sentPayloads[1]).toEqual({ cau_hoi: 'Câu hỏi 2', nhan_dinh_id: 'nd-1' })
    expect(sentPayloads[2]).toEqual({ cau_hoi: 'Câu hỏi chung', nhan_dinh_id: null })

    const caseMessages = render().getMessages('DEMO-02')
    expect(caseMessages).toHaveLength(4)
    expect(caseMessages.map((msg) => msg.vai)).toEqual([
      'nguoi_dung',
      'he_thong',
      'nguoi_dung',
      'he_thong',
    ])
    const globalMessages = render().getMessages('__global__')
    expect(globalMessages).toHaveLength(2)
    expect(globalMessages.map((msg) => msg.vai)).toEqual(['nguoi_dung', 'he_thong'])
    expect(render().askedCaseIds).toEqual(['__global__', 'DEMO-02'])
  })

  it('retryLastQuestion cũng không gửi khoá lich_su', async () => {
    const sentPayloads: GuiCauHoi[] = []
    const client = new MockClient({ delayMs: 0, askDelayMs: 0 })
    vi.spyOn(client, 'ask')
      .mockRejectedValueOnce(new ApiError('loi_he_thong', 'Mất kết nối', 500))
      .mockImplementation(async (_caId, payload) => {
        sentPayloads.push(payload)
        return sampleReply
      })

    const runner = hooks.create()
    cleanups.push(runner.unmount)
    const render = () => runner.render(() => useChat(client, 'DEMO-02'))

    await render().sendQuestion('DEMO-02', 'Câu hỏi cần gửi lại')
    expect(render().getLastStatus('DEMO-02')).toBe('loi')

    await render().retryLastQuestion('DEMO-02')
    expect(sentPayloads).toHaveLength(1)
    expect('lich_su' in sentPayloads[0]).toBe(false)
    expect(sentPayloads[0]).toEqual({ cau_hoi: 'Câu hỏi cần gửi lại', nhan_dinh_id: null })
    expect(render().getLastStatus('DEMO-02')).toBe('ok')
  })
})

describe('formatAskErrorMessage xử lý lỗi 429', () => {
  it('hiện thông báo thân thiện kèm số giây chờ khi nhận 429 vuot_gioi_han', () => {
    const err = new ApiError(
      'vuot_gioi_han',
      'Bạn đã gửi quá nhiều câu hỏi. Vui lòng thử lại sau 45 giây.',
      429,
    )
    const msg = formatAskErrorMessage(err)
    expect(msg).toContain('45 giây')
    expect(msg).toContain('quá nhiều')
  })

  it('hiện thông báo thân thiện kèm số giây chờ khi nhận 429 het_ngan_sach_ngay', () => {
    const err = new ApiError(
      'het_ngan_sach_ngay',
      'Hệ thống đã đạt giới hạn lượt LLM trong ngày. Vui lòng thử lại sau 120 giây.',
      429,
    )
    const msg = formatAskErrorMessage(err)
    expect(msg).toContain('120 giây')
    expect(msg).toContain('trong ngày')
  })

  it('vẫn có số giây chờ mặc định khi 429 không nêu rõ số giây', () => {
    const err = new ApiError('vuot_gioi_han', 'Too Many Requests', 429)
    const msg = formatAskErrorMessage(err)
    expect(msg).toMatch(/\d+\s*giây/)
  })

  it('giữ nguyên thông điệp với lỗi khác 429', () => {
    expect(formatAskErrorMessage(new ApiError('loi_he_thong', 'Lỗi máy chủ', 500))).toBe(
      'Lỗi máy chủ',
    )
    expect(formatAskErrorMessage(null)).toBe('Không thể gửi câu hỏi tới máy chủ.')
  })
})

function makeAskStep(
  ma: string,
  ten: string,
  trang_thai: BuocAI['trang_thai'],
  overrides: Partial<BuocAI> = {},
): BuocAI {
  return {
    ma,
    ten,
    trang_thai,
    chi_tiet: null,
    nguon: [],
    thoi_gian_ms: null,
    ly_do: null,
    goi_y: null,
    ...overrides,
  }
}

describe('useChat tiến trình hỏi đáp 1000 ms, tạm dừng khi ẩn tab và chống đua ca', () => {
  let visibility: EventTarget & { hidden: boolean }

  beforeEach(() => {
    vi.useFakeTimers()
    visibility = Object.assign(new EventTarget(), { hidden: false })
    vi.stubGlobal('document', visibility)
  })

  afterEach(() => {
    for (const cleanup of cleanups.splice(0)) cleanup()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('hỏi getAskProgress mỗi 1000 ms, dừng khi tab ẩn rồi hỏi ngay khi hiện, gắn cac_buoc khi xong', async () => {
    expect(ASK_PROGRESS_POLL_INTERVAL_MS).toBe(1000)

    let resolveAsk!: (value: TraLoi) => void
    const ask = vi.fn<ReviewApiClient['ask']>(
      () =>
        new Promise<TraLoi>((resolve) => {
          resolveAsk = resolve
        }),
    )

    const runningStep = makeAskStep('truy_xuat', 'Tra cứu nguồn', 'dang_chay', {
      thoi_gian_ms: 400,
    })
    const doneSteps: BuocAI[] = [
      makeAskStep('chuan_bi', 'Chuẩn bị ngữ cảnh ca', 'xong', { thoi_gian_ms: 150 }),
      makeAskStep('truy_xuat', 'Tra cứu nguồn', 'xong', { thoi_gian_ms: 600 }),
      makeAskStep('goi_mo_hinh', 'Soạn câu trả lời', 'xong', { thoi_gian_ms: 900 }),
      makeAskStep('kiem_chung', 'Kiểm chứng trích dẫn và số liệu', 'xong', {
        chi_tiet: 'kiểm chứng đạt',
        thoi_gian_ms: 250,
      }),
    ]

    const getAskProgress = vi
      .fn<ReviewApiClient['getAskProgress']>()
      .mockResolvedValueOnce({
        dang_chay: true,
        cac_buoc: [runningStep],
        da_chay_ms: 1000,
      })
      .mockResolvedValueOnce({
        dang_chay: true,
        cac_buoc: [
          makeAskStep('truy_xuat', 'Tra cứu nguồn', 'xong', { thoi_gian_ms: 600 }),
          makeAskStep('goi_mo_hinh', 'Soạn câu trả lời', 'dang_chay', { thoi_gian_ms: 400 }),
        ],
        da_chay_ms: 2000,
      })
      .mockResolvedValueOnce({
        dang_chay: false,
        cac_buoc: doneSteps,
        da_chay_ms: 2400,
      })

    const client = { ask, getAskProgress } as unknown as ReviewApiClient
    const runner = hooks.create()
    cleanups.push(runner.unmount)
    const render = () => runner.render(() => useChat(client, 'DEMO-02'))

    const sendPromise = render().sendQuestion('DEMO-02', 'Vì sao chỉnh liều?')

    await vi.advanceTimersByTimeAsync(999)
    expect(getAskProgress).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(getAskProgress).toHaveBeenCalledTimes(1)
    expect(getAskProgress).toHaveBeenCalledWith('DEMO-02', expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(render().getProgress('DEMO-02')).toEqual({
      cacBuoc: [runningStep],
      daChayMs: 1000,
    })

    visibility.hidden = true
    visibility.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(5000)
    expect(getAskProgress).toHaveBeenCalledTimes(1)

    visibility.hidden = false
    visibility.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(getAskProgress).toHaveBeenCalledTimes(2)
    expect(render().getProgress('DEMO-02').daChayMs).toBe(2000)

    resolveAsk(sampleReply)
    await sendPromise

    expect(getAskProgress).toHaveBeenCalledTimes(3)
    expect(render().isSending('DEMO-02')).toBe(false)
    expect(render().getProgress('DEMO-02')).toEqual({ cacBuoc: [], daChayMs: null })

    const msgs = render().getMessages('DEMO-02')
    const assistant = msgs[1]
    expect(assistant?.vai).toBe('he_thong')
    if (assistant?.vai === 'he_thong') {
      expect(assistant.cac_buoc).toEqual(doneSteps)
      expect(assistant.da_chay_ms).toBe(2400)
    }

    await vi.advanceTimersByTimeAsync(5000)
    expect(getAskProgress).toHaveBeenCalledTimes(3)
  })

  it('dừng hỏi tiến trình khi stopQuestion hoặc clearChat', async () => {
    const ask = vi.fn<ReviewApiClient['ask']>(
      (_caId, _payload, options) =>
        new Promise<TraLoi>((_resolve, reject) => {
          options?.signal?.addEventListener('abort', () => {
            reject(new DOMException('Đã huỷ.', 'AbortError'))
          })
        }),
    )
    const getAskProgress = vi.fn<ReviewApiClient['getAskProgress']>(async () => ({
      dang_chay: true,
      cac_buoc: [makeAskStep('chuan_bi', 'Chuẩn bị ngữ cảnh ca', 'dang_chay')],
      da_chay_ms: 1000,
    }))

    const client = { ask, getAskProgress } as unknown as ReviewApiClient
    const runner = hooks.create()
    cleanups.push(runner.unmount)
    const render = () => runner.render(() => useChat(client, 'DEMO-02'))

    const p1 = render().sendQuestion('DEMO-02', 'Câu hỏi 1')
    await vi.advanceTimersByTimeAsync(1000)
    expect(getAskProgress).toHaveBeenCalledTimes(1)

    render().stopQuestion('DEMO-02')
    await p1
    expect(render().isSending('DEMO-02')).toBe(false)
    expect(render().getProgress('DEMO-02')).toEqual({ cacBuoc: [], daChayMs: null })

    await vi.advanceTimersByTimeAsync(3000)
    expect(getAskProgress).toHaveBeenCalledTimes(1)

    const p2 = render().sendQuestion('DEMO-02', 'Câu hỏi 2')
    await vi.advanceTimersByTimeAsync(1000)
    expect(getAskProgress).toHaveBeenCalledTimes(2)

    render().clearChat('DEMO-02')
    await p2
    expect(render().getMessages('DEMO-02')).toEqual([])
    await vi.advanceTimersByTimeAsync(3000)
    expect(getAskProgress).toHaveBeenCalledTimes(2)
  })

  it('hai ca đổi nhanh dừng polling ca cũ và không lẫn bước sang ca mới', async () => {
    let resolveOldAsk!: (value: TraLoi) => void
    const ask = vi.fn<ReviewApiClient['ask']>((caId) => {
      if (caId === 'DEMO-02') {
        return new Promise<TraLoi>((resolve) => {
          resolveOldAsk = resolve
        })
      }
      return Promise.resolve(sampleReply)
    })

    const getAskProgress = vi.fn<ReviewApiClient['getAskProgress']>(async (caId): Promise<TienTrinhHoiDap> => {
      if (caId === 'DEMO-02') {
        return {
          dang_chay: true,
          cac_buoc: [makeAskStep('chuan_bi', 'Bước ca cũ rò sang', 'dang_chay')],
          da_chay_ms: 1000,
        }
      }
      return {
        dang_chay: false,
        cac_buoc: [makeAskStep('chuan_bi', 'Bước ca mới', 'xong')],
        da_chay_ms: 200,
      }
    })

    const client = { ask, getAskProgress } as unknown as ReviewApiClient
    const runner = hooks.create()
    cleanups.push(runner.unmount)
    let activeCase = 'DEMO-02'
    const render = () => runner.render(() => useChat(client, activeCase))

    const oldPromise = render().sendQuestion('DEMO-02', 'Câu hỏi ca cũ')
    await vi.advanceTimersByTimeAsync(1000)
    expect(getAskProgress).toHaveBeenCalledTimes(1)
    expect(render().getProgress('DEMO-02').cacBuoc[0]?.ten).toBe('Bước ca cũ rò sang')

    activeCase = 'DEMO-06'
    render()

    await vi.advanceTimersByTimeAsync(3000)
    expect(getAskProgress).toHaveBeenCalledTimes(1)

    await render().sendQuestion('DEMO-06', 'Câu hỏi ca mới')
    resolveOldAsk(sampleReply)
    await oldPromise

    const oldMsgs = render().getMessages('DEMO-02')
    expect(oldMsgs).toHaveLength(1)
    expect(oldMsgs[0].vai).toBe('nguoi_dung')

    const newMsgs = render().getMessages('DEMO-06')
    expect(newMsgs).toHaveLength(2)
    if (newMsgs[1].vai === 'he_thong') {
      expect(newMsgs[1].cac_buoc?.[0]?.ten).toBe('Bước ca mới')
    }
  })

  it('gắn bước lỗi khi thất bại, hỗ trợ retryLastQuestion và không gắn bước cho lịch sử khôi phục', async () => {
    const errSteps: BuocAI[] = [
      makeAskStep('chuan_bi', 'Chuẩn bị ngữ cảnh ca', 'xong', { thoi_gian_ms: 100 }),
      makeAskStep('goi_mo_hinh', 'Soạn câu trả lời', 'loi', {
        ly_do: 'Quá hạn chờ',
        goi_y: 'Thử lại sau',
      }),
    ]
    const okSteps: BuocAI[] = [
      makeAskStep('chuan_bi', 'Chuẩn bị ngữ cảnh ca', 'xong', { thoi_gian_ms: 100 }),
      makeAskStep('goi_mo_hinh', 'Soạn câu trả lời', 'xong', { thoi_gian_ms: 300 }),
    ]

    const ask = vi
      .fn<ReviewApiClient['ask']>()
      .mockRejectedValueOnce(new ApiError('loi_mo_hinh', 'Lỗi tạm thời', 503))
      .mockResolvedValueOnce(sampleReply)

    const getAskProgress = vi
      .fn<ReviewApiClient['getAskProgress']>()
      .mockResolvedValueOnce({ dang_chay: false, cac_buoc: errSteps, da_chay_ms: 900 })
      .mockResolvedValueOnce({ dang_chay: false, cac_buoc: okSteps, da_chay_ms: 400 })

    const getConversations = vi.fn<NonNullable<ReviewApiClient['getConversations']>>(async () => ({
      'DEMO-01': [{ cau_hoi: 'Câu cũ', tra_loi: sampleReply }],
    }))

    const client = { ask, getAskProgress, getConversations } as unknown as ReviewApiClient
    const runner = hooks.create()
    cleanups.push(runner.unmount)
    const render = () => runner.render(() => useChat(client, 'DEMO-02'))

    render()
    await vi.advanceTimersByTimeAsync(0)
    const restored = render().getMessages('DEMO-01')
    expect(restored).toHaveLength(2)
    if (restored[1].vai === 'he_thong') {
      expect(restored[1].cac_buoc).toBeUndefined()
    }

    await render().sendQuestion('DEMO-02', 'Câu hỏi gặp lỗi')
    const afterErr = render().getMessages('DEMO-02')
    expect(afterErr).toHaveLength(2)
    if (afterErr[1].vai === 'he_thong') {
      expect(afterErr[1].tra_loi.trang_thai).toBe('loi')
      expect(afterErr[1].cac_buoc).toEqual(errSteps)
    }

    await render().retryLastQuestion('DEMO-02')
    const afterRetry = render().getMessages('DEMO-02')
    expect(afterRetry).toHaveLength(2)
    if (afterRetry[1].vai === 'he_thong') {
      expect(afterRetry[1].tra_loi.trang_thai).toBe('ok')
      expect(afterRetry[1].cac_buoc).toEqual(okSteps)
    }
  })
})
