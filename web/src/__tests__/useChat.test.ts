import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client.ts'
import { MockClient } from '../api/mock.ts'
import type { GuiCauHoi, TraLoi } from '../api/types.ts'
import { formatAskErrorMessage, useChat } from '../state/useChat.ts'

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
