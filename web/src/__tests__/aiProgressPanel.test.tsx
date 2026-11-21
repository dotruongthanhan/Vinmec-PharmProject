import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReviewApiClient } from '../api/client.ts'
import type { BuocAI, KetQuaAI } from '../api/types.ts'
import { AiProgressPanel } from '../features/findings/AiProgressPanel.tsx'
import { AiStatusBar } from '../features/findings/AiStatusBar.tsx'
import { pickStepStatusAnnouncement } from '../lib/aiReview.ts'
import {
  AI_POLL_INTERVAL_MS,
  runAiReviewSession,
} from '../state/useAiReview.ts'
import type { AiRunSnapshot } from '../state/useAiReview.ts'

const SAMPLE_STEPS_RUNNING: BuocAI[] = [
  {
    ma: 'thu_thap_nguon',
    ten: 'Lấy nguồn',
    trang_thai: 'xong',
    chi_tiet: '12 đoạn',
    nguon: [
      { nhan: 'openFDA', so_doan: 6 },
      { nhan: 'Bộ Y tế', so_doan: 4 },
      { nhan: 'DDInter', so_doan: 2 },
    ],
    thoi_gian_ms: 1200,
    ly_do: null,
    goi_y: null,
  },
  {
    ma: 'tong_hop_1',
    ten: 'Tổng hợp nhận định',
    trang_thai: 'dang_chay',
    chi_tiet: 'đang gọi mô hình…',
    nguon: [],
    thoi_gian_ms: 8400,
    ly_do: null,
    goi_y: null,
  },
  {
    ma: 'kiem_chung_1',
    ten: 'Kiểm chứng trích dẫn',
    trang_thai: 'cho',
    chi_tiet: null,
    nguon: [],
    thoi_gian_ms: null,
    ly_do: null,
    goi_y: null,
  },
]

const SAMPLE_STEPS_ALL_STATUSES: BuocAI[] = [
  ...SAMPLE_STEPS_RUNNING,
  {
    ma: 'tong_hop_2',
    ten: 'Tổng hợp lại',
    trang_thai: 'loi',
    chi_tiet: 'TimeoutError',
    nguon: [],
    thoi_gian_ms: 2100,
    ly_do: 'Hết thời gian chờ nhà cung cấp.',
    goi_y: 'Thử lại sau ít phút.',
  },
  {
    ma: 'kiem_chung_2',
    ten: 'Kiểm chứng lại',
    trang_thai: 'bo_qua',
    chi_tiet: null,
    nguon: [],
    thoi_gian_ms: null,
    ly_do: null,
    goi_y: null,
  },
]

function makeKetQua(overrides: Partial<KetQuaAI>): KetQuaAI {
  return {
    trang_thai: 'dang_chay',
    nhan_dinh: null,
    canh_bao: [],
    thoi_gian_ms: null,
    mo_hinh: null,
    cac_buoc: [],
    da_chay_ms: null,
    thuong_le_ms: null,
    ...overrides,
  }
}

describe('AiProgressPanel và AiStatusBar', () => {
  it('hiển thị đầy đủ 5 trạng thái bước, nguồn, đồng hồ aria-hidden, aria-live không chứa giây và lớp motion-safe', () => {
    const html = renderToStaticMarkup(
      <AiProgressPanel
        trangThai="dang_chay"
        cacBuoc={SAMPLE_STEPS_ALL_STATUSES}
        daChayMs={14_000}
        thuongLeMs={25_000}
      />,
    )

    expect(html).toContain('AI đang phân tích ca này')
    expect(html).toContain('Lấy nguồn')
    expect(html).toContain('(xong)')
    expect(html).toContain('Tổng hợp nhận định')
    expect(html).toContain('(đang chạy)')
    expect(html).toContain('Kiểm chứng trích dẫn')
    expect(html).toContain('(chờ)')
    expect(html).toContain('Tổng hợp lại')
    expect(html).toContain('(lỗi)')
    expect(html).toContain('Kiểm chứng lại')
    expect(html).toContain('(bỏ qua)')
    expect(html).toContain('opacity-55')

    expect(html).toContain('12 đoạn')
    expect(html).toContain('openFDA')
    expect(html).toContain('6')
    expect(html).toContain('Bộ Y tế')
    expect(html).toContain('4')
    expect(html).toContain('DDInter')
    expect(html).toContain('2')
    expect(html).toContain('1,2s')
    expect(html).toContain('8,4s')
    expect(html).toContain('14s')
    expect(html).toContain('thường 20–40 s')

    expect(html).toContain('motion-safe:animate-spin')
    expect(html).not.toMatch(/class="[^"]*\sanimate-spin(\s|")/)
    expect(html).toContain('Bảng bên dưới là kết quả của bộ luật.')

    const liveMatch = /aria-live="polite"[^>]*>([^<]*)<\/div>/.exec(html)
    expect(liveMatch).not.toBeNull()
    expect(liveMatch?.[1]).toBe('Bước Tổng hợp lại: lỗi')
    expect(liveMatch?.[1]).not.toMatch(/\d+s/)
  })

  it('không hiện dòng thường mất khi thiếu thuong_le_ms và hiện cảnh báo chậm khi bước quá 30 s', () => {
    const slowSteps: BuocAI[] = [
      SAMPLE_STEPS_RUNNING[0],
      {
        ...SAMPLE_STEPS_RUNNING[1],
        thoi_gian_ms: 31_000,
      },
      SAMPLE_STEPS_RUNNING[2],
    ]

    const html = renderToStaticMarkup(
      <AiProgressPanel
        trangThai="dang_chay"
        cacBuoc={slowSteps}
        daChayMs={32_200}
        thuongLeMs={null}
      />,
    )

    expect(html).not.toMatch(/thường \d/)
    expect(html).toContain('role="status"')
    expect(html).toContain('Bước Tổng hợp nhận định đang lâu hơn thường lệ. Bảng luật vẫn dùng được.')
  })

  it('nhánh lỗi dùng nền warning, hiện lý do, gợi ý, nút Thử lại, giữ ✓ ở bước xong và làm mờ bước bỏ qua', () => {
    const errorSteps: BuocAI[] = [
      SAMPLE_STEPS_RUNNING[0],
      {
        ma: 'tong_hop_1',
        ten: 'Tổng hợp nhận định',
        trang_thai: 'loi',
        chi_tiet: 'TimeoutError',
        nguon: [],
        thoi_gian_ms: 9500,
        ly_do: 'Nhà cung cấp mô hình quá tải.',
        goi_y: 'Dùng bảng luật bên dưới và bấm Thử lại.',
      },
      {
        ma: 'kiem_chung_1',
        ten: 'Kiểm chứng trích dẫn',
        trang_thai: 'bo_qua',
        chi_tiet: null,
        nguon: [],
        thoi_gian_ms: null,
        ly_do: null,
        goi_y: null,
      },
    ]

    const html = renderToStaticMarkup(
      <AiStatusBar
        trangThai="loi"
        thoiGianMs={10_700}
        coDienGiai={0}
        doAiThem={0}
        canhBao={['Không gọi được mô hình.']}
        onRerun={() => {}}
        cacBuoc={errorSteps}
        daChayMs={10_700}
        thuongLeMs={25_000}
      />,
    )

    expect(html).toContain('role="alert"')
    expect(html).toContain('bg-warning-bg')
    expect(html).toContain('border-warning-line')
    expect(html).toContain('Thử lại')
    expect(html).toContain('Nhà cung cấp mô hình quá tải.')
    expect(html).toContain('Dùng bảng luật bên dưới và bấm Thử lại.')
    expect(html).toContain('text-success-fg')
    expect(html).toContain('opacity-55')
  })

  it('nhánh xong mặc định thu gọn, mở được khi bật, và ẩn nút Xem các bước khi cac_buoc rỗng', () => {
    const doneSteps: BuocAI[] = SAMPLE_STEPS_RUNNING.map((step) => ({
      ...step,
      trang_thai: 'xong',
      thoi_gian_ms: step.thoi_gian_ms ?? 1000,
    }))

    const collapsedHtml = renderToStaticMarkup(
      <AiStatusBar
        trangThai="xong"
        thoiGianMs={12_000}
        coDienGiai={2}
        doAiThem={1}
        canhBao={[]}
        onRerun={() => {}}
        cacBuoc={doneSteps}
        daChayMs={12_000}
        thuongLeMs={25_000}
      />,
    )
    expect(collapsedHtml).toContain('AI đã phân tích xong (12 giây).')
    expect(collapsedHtml).toContain('Xem các bước (3)')
    expect(collapsedHtml).toContain('aria-expanded="false"')
    expect(collapsedHtml).toContain('aria-controls=')
    expect(collapsedHtml).toContain('Chạy lại')
    expect(collapsedHtml).not.toContain('Kiểm chứng trích dẫn')

    const expandedHtml = renderToStaticMarkup(
      <AiProgressPanel
        trangThai="xong"
        cacBuoc={doneSteps}
        daChayMs={12_000}
        thuongLeMs={25_000}
        thoiGianMs={12_000}
        summaryText="AI đã phân tích xong (12 giây)."
        onRerun={() => {}}
        defaultExpanded
      />,
    )
    expect(expandedHtml).toContain('Ẩn các bước')
    expect(expandedHtml).toContain('aria-expanded="true"')
    expect(expandedHtml).toContain('Kiểm chứng trích dẫn')

    const legacyEmptyHtml = renderToStaticMarkup(
      <AiStatusBar
        trangThai="xong"
        thoiGianMs={3000}
        coDienGiai={1}
        doAiThem={0}
        canhBao={[]}
        onRerun={() => {}}
      />,
    )
    expect(legacyEmptyHtml).toContain('AI đã phân tích xong (3 giây).')
    expect(legacyEmptyHtml).not.toContain('Xem các bước')
  })

  it('thoát chuỗi HTML từ API thành văn bản thuần và cập nhật câu thông báo khi bước đổi trạng thái', () => {
    const xssSteps: BuocAI[] = [
      {
        ma: 'thu_thap_nguon',
        ten: 'Lấy nguồn <script>alert(1)</script>',
        trang_thai: 'dang_chay',
        chi_tiet: '<img src=x onerror=alert(1)>',
        nguon: [],
        thoi_gian_ms: 500,
        ly_do: null,
        goi_y: null,
      },
    ]

    const html = renderToStaticMarkup(
      <AiProgressPanel
        trangThai="dang_chay"
        cacBuoc={xssSteps}
        daChayMs={500}
        thuongLeMs={null}
      />,
    )

    expect(html).not.toContain('<script>')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')

    const msg1 = pickStepStatusAnnouncement(
      [SAMPLE_STEPS_RUNNING[1]],
      { thu_thap_nguon: 'dang_chay', tong_hop_1: 'cho', kiem_chung_1: 'cho' },
    )
    expect(msg1).toBe('Bước Tổng hợp nhận định: đang chạy')

    const msgUnchanged = pickStepStatusAnnouncement(
      [{ ...SAMPLE_STEPS_RUNNING[1], thoi_gian_ms: 9500 }],
      { tong_hop_1: 'dang_chay' },
    )
    expect(msgUnchanged).toBe('')
  })
})

describe('useAiReview polling 1500 ms, tạm dừng khi ẩn tab và chống đua ca', () => {
  let visibility: EventTarget & { hidden: boolean }

  beforeEach(() => {
    vi.useFakeTimers()
    visibility = Object.assign(new EventTarget(), { hidden: false })
    vi.stubGlobal('document', visibility)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('hỏi lại mỗi 1500 ms, cập nhật bước theo từng lượt và tạm dừng khi tab ẩn rồi hỏi ngay khi hiện', async () => {
    expect(AI_POLL_INTERVAL_MS).toBe(1500)

    const startAi = vi.fn<ReviewApiClient['startAi']>(async () =>
      makeKetQua({
        trang_thai: 'dang_chay',
        cac_buoc: [
          { ...SAMPLE_STEPS_RUNNING[0], trang_thai: 'dang_chay', chi_tiet: null, nguon: [], thoi_gian_ms: 100 },
          SAMPLE_STEPS_RUNNING[2],
        ],
        da_chay_ms: 100,
        thuong_le_ms: 25_000,
      }),
    )
    const getAi = vi
      .fn<ReviewApiClient['getAi']>()
      .mockResolvedValueOnce(
        makeKetQua({
          trang_thai: 'dang_chay',
          cac_buoc: SAMPLE_STEPS_RUNNING,
          da_chay_ms: 1600,
          thuong_le_ms: 25_000,
        }),
      )
      .mockResolvedValueOnce(
        makeKetQua({
          trang_thai: 'xong',
          thoi_gian_ms: 3100,
          cac_buoc: SAMPLE_STEPS_RUNNING.map((s) => ({ ...s, trang_thai: 'xong' })),
          da_chay_ms: 3100,
          thuong_le_ms: 25_000,
        }),
      )

    const client = { startAi, getAi } as unknown as ReviewApiClient
    const snapshots: AiRunSnapshot[] = []

    const stop = runAiReviewSession({
      caId: 'DEMO-02',
      runKey: 'DEMO-02::0',
      isRerun: false,
      client,
      isCurrent: () => true,
      onUpdate: (snap) => snapshots.push(snap),
    })

    await vi.advanceTimersByTimeAsync(0)
    expect(startAi).toHaveBeenCalledTimes(1)
    expect(snapshots).toHaveLength(1)
    expect(snapshots[0].cacBuoc[0].trang_thai).toBe('dang_chay')

    await vi.advanceTimersByTimeAsync(1499)
    expect(getAi).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(getAi).toHaveBeenCalledTimes(1)
    expect(snapshots).toHaveLength(2)
    expect(snapshots[1].cacBuoc[1].trang_thai).toBe('dang_chay')
    expect(snapshots[1].daChayMs).toBe(1600)

    visibility.hidden = true
    visibility.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(10_000)
    expect(getAi).toHaveBeenCalledTimes(1)

    visibility.hidden = false
    visibility.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(getAi).toHaveBeenCalledTimes(2)
    expect(snapshots).toHaveLength(3)
    expect(snapshots[2].trangThai).toBe('xong')

    stop()
  })

  it('đổi ca nhanh không để bước của ca cũ ghi đè ca mới và chịu được thiếu cac_buoc', async () => {
    let resolveOldGet!: (value: KetQuaAI | null) => void
    const oldGetPromise = new Promise<KetQuaAI | null>((resolve) => {
      resolveOldGet = resolve
    })

    const startAi = vi.fn<ReviewApiClient['startAi']>(async (caId) => {
      if (caId === 'DEMO-02') {
        return makeKetQua({
          trang_thai: 'dang_chay',
          cac_buoc: SAMPLE_STEPS_RUNNING,
          da_chay_ms: 500,
        })
      }
      return {
        trang_thai: 'dang_chay',
        nhan_dinh: null,
        canh_bao: [],
        thoi_gian_ms: null,
        mo_hinh: null,
      } as unknown as KetQuaAI
    })

    const getAi = vi.fn<ReviewApiClient['getAi']>((caId) => {
      if (caId === 'DEMO-02') {
        return oldGetPromise
      }
      return Promise.resolve(
        makeKetQua({
          trang_thai: 'dang_chay',
          cac_buoc: [
            {
              ma: 'thu_thap_nguon',
              ten: 'Lấy nguồn ca mới',
              trang_thai: 'dang_chay',
              chi_tiet: null,
              nguon: [],
              thoi_gian_ms: 400,
              ly_do: null,
              goi_y: null,
            },
          ],
          da_chay_ms: 400,
        }),
      )
    })

    const client = { startAi, getAi } as unknown as ReviewApiClient
    let activeCase = 'DEMO-02'
    const snapshotsByCase: Record<string, AiRunSnapshot> = {}

    const stopOld = runAiReviewSession({
      caId: 'DEMO-02',
      runKey: 'DEMO-02::0',
      isRerun: false,
      client,
      isCurrent: () => activeCase === 'DEMO-02',
      onUpdate: (snap) => {
        snapshotsByCase[snap.caId] = snap
      },
    })

    await vi.advanceTimersByTimeAsync(1500)
    expect(getAi).toHaveBeenCalledWith('DEMO-02')

    activeCase = 'DEMO-06'
    stopOld()

    const stopNew = runAiReviewSession({
      caId: 'DEMO-06',
      runKey: 'DEMO-06::0',
      isRerun: false,
      client,
      isCurrent: () => activeCase === 'DEMO-06',
      onUpdate: (snap) => {
        snapshotsByCase[snap.caId] = snap
      },
    })

    await vi.advanceTimersByTimeAsync(0)
    expect(snapshotsByCase['DEMO-06']?.cacBuoc).toEqual([])

    resolveOldGet(
      makeKetQua({
        trang_thai: 'xong',
        cac_buoc: [{ ...SAMPLE_STEPS_RUNNING[0], ten: 'Bước ca cũ rò sang' }],
      }),
    )
    await vi.advanceTimersByTimeAsync(0)
    expect(snapshotsByCase['DEMO-02']?.trangThai).not.toBe('xong')
    expect(snapshotsByCase['DEMO-06']?.cacBuoc).toEqual([])

    await vi.advanceTimersByTimeAsync(1500)
    expect(snapshotsByCase['DEMO-06']?.cacBuoc[0]?.ten).toBe('Lấy nguồn ca mới')

    stopNew()
  })
})
