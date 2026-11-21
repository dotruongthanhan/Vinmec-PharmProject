import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, normalizeTienTrinhHoiDap } from '../api/client.ts'
import type { FetchLike, ReviewApiClient } from '../api/client.ts'
import { MockClient } from '../api/mock.ts'
import { MOCK_CASE_DETAILS } from '../api/mockData.ts'
import type { BuocAI } from '../api/types.ts'
import { TooltipProvider } from '../components/ui/tooltip.tsx'
import {
  AssistantMessageSteps,
  AssistantPanel,
} from '../features/assistant/AssistantPanel.tsx'
import type { ChatMessage } from '../state/useChat.ts'

const SAMPLE_ASK_STEPS_RUNNING: BuocAI[] = [
  {
    ma: 'chuan_bi',
    ten: 'Chuẩn bị ngữ cảnh ca',
    trang_thai: 'xong',
    chi_tiet: 'đã sẵn sàng',
    nguon: [],
    thoi_gian_ms: 200,
    ly_do: null,
    goi_y: null,
  },
  {
    ma: 'truy_xuat',
    ten: 'Tra cứu nguồn',
    trang_thai: 'xong',
    chi_tiet: '8 đoạn từ 2 nguồn',
    nguon: [
      { nhan: 'openFDA', so_doan: 5 },
      { nhan: 'Bộ Y tế', so_doan: 3 },
    ],
    thoi_gian_ms: 450,
    ly_do: null,
    goi_y: null,
  },
  {
    ma: 'goi_mo_hinh',
    ten: 'Soạn câu trả lời',
    trang_thai: 'dang_chay',
    chi_tiet: 'đang gọi mô hình…',
    nguon: [],
    thoi_gian_ms: 700,
    ly_do: null,
    goi_y: null,
  },
  {
    ma: 'kiem_chung',
    ten: 'Kiểm chứng trích dẫn và số liệu',
    trang_thai: 'cho',
    chi_tiet: null,
    nguon: [],
    thoi_gian_ms: null,
    ly_do: null,
    goi_y: null,
  },
]

const SAMPLE_ASK_STEPS_DONE: BuocAI[] = [
  ...SAMPLE_ASK_STEPS_RUNNING.slice(0, 2),
  {
    ma: 'goi_mo_hinh',
    ten: 'Soạn câu trả lời',
    trang_thai: 'xong',
    chi_tiet: 'đã soạn câu trả lời',
    nguon: [],
    thoi_gian_ms: 900,
    ly_do: null,
    goi_y: null,
  },
  {
    ma: 'kiem_chung',
    ten: 'Kiểm chứng trích dẫn và số liệu',
    trang_thai: 'xong',
    chi_tiet: 'kiểm chứng đạt',
    nguon: [],
    thoi_gian_ms: 250,
    ly_do: null,
    goi_y: null,
  },
]

const SAMPLE_ASK_STEPS_ERROR: BuocAI[] = [
  ...SAMPLE_ASK_STEPS_RUNNING.slice(0, 2),
  {
    ma: 'goi_mo_hinh',
    ten: 'Soạn câu trả lời',
    trang_thai: 'loi',
    chi_tiet: 'TimeoutError',
    nguon: [],
    thoi_gian_ms: 850,
    ly_do: 'Nhà cung cấp mô hình tạm thời không phản hồi đúng hạn.',
    goi_y: 'Thử gửi lại câu hỏi sau ít phút hoặc kiểm tra lại đoạn nguồn.',
  },
  {
    ma: 'kiem_chung',
    ten: 'Kiểm chứng trích dẫn và số liệu',
    trang_thai: 'bo_qua',
    chi_tiet: null,
    nguon: [],
    thoi_gian_ms: null,
    ly_do: null,
    goi_y: null,
  },
]

function renderAssistant(props: Partial<Parameters<typeof AssistantPanel>[0]> = {}): string {
  const client = new MockClient({ delayMs: 0, askDelayMs: 0 })
  return renderToStaticMarkup(
    <TooltipProvider>
      <AssistantPanel
        client={client}
        detail={MOCK_CASE_DETAILS['DEMO-02']}
        history={[]}
        onOpenHistory={() => {}}
        attentionFindings={MOCK_CASE_DETAILS['DEMO-02'].nhan_dinh.can_chu_y}
        messages={[]}
        sending={false}
        lastStatus={null}
        focusedFinding={null}
        onClearFocusedFinding={() => {}}
        onSend={async () => {}}
        onStop={() => {}}
        onRetryLast={async () => {}}
        onClear={() => {}}
        onClose={() => {}}
        onOpenEvidence={() => {}}
        {...props}
      />
    </TooltipProvider>,
  )
}

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('ApiClient.getAskProgress và chuẩn hoá phản hồi', () => {
  it('dùng đúng đường dẫn theo ca và đường dẫn chung /ask/tien-trinh cho __global__', async () => {
    const urls: string[] = []
    const fakeFetch: FetchLike = async (input) => {
      urls.push(String(input))
      return new Response(
        JSON.stringify({
          dang_chay: true,
          cac_buoc: SAMPLE_ASK_STEPS_RUNNING,
          da_chay_ms: 1350,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }

    const client: ReviewApiClient = new ApiClient('/api', fakeFetch)
    const caseRes = await client.getAskProgress('DEMO-02')
    const globalRes = await client.getAskProgress('__global__')

    expect(urls).toEqual(['/api/cases/DEMO-02/ask/tien-trinh', '/api/ask/tien-trinh'])
    expect(caseRes.dang_chay).toBe(true)
    expect(caseRes.cac_buoc).toHaveLength(4)
    expect(caseRes.da_chay_ms).toBe(1350)
    expect(globalRes.dang_chay).toBe(true)
  })

  it('chuẩn hoá phản hồi thiếu trường và không ném lỗi khi gặp 404 hoặc lỗi mạng', async () => {
    expect(normalizeTienTrinhHoiDap(null)).toEqual({
      dang_chay: false,
      cac_buoc: [],
      da_chay_ms: null,
    })
    expect(normalizeTienTrinhHoiDap({})).toEqual({
      dang_chay: false,
      cac_buoc: [],
      da_chay_ms: null,
    })
    expect(
      normalizeTienTrinhHoiDap({
        dang_chay: true,
        cac_buoc: [{ ma: 'chuan_bi', ten: 'Chuẩn bị', trang_thai: 'khong_hop_le' }],
      }),
    ).toEqual({
      dang_chay: true,
      cac_buoc: [
        {
          ma: 'chuan_bi',
          ten: 'Chuẩn bị',
          trang_thai: 'cho',
          chi_tiet: null,
          nguon: [],
          thoi_gian_ms: null,
          ly_do: null,
          goi_y: null,
        },
      ],
      da_chay_ms: null,
    })

    const notFoundClient = new ApiClient('/api', async () =>
      new Response(JSON.stringify({ loi: { ma: 'khong_tim_thay', thong_bao: 'Không thấy' } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await expect(notFoundClient.getAskProgress('DEMO-02')).resolves.toEqual({
      dang_chay: false,
      cac_buoc: [],
      da_chay_ms: null,
    })

    const offlineClient = new ApiClient('/api', async () => {
      throw new TypeError('Failed to fetch')
    })
    await expect(offlineClient.getAskProgress('__global__')).resolves.toEqual({
      dang_chay: false,
      cac_buoc: [],
      da_chay_ms: null,
    })
  })
})

describe('MockClient.getAskProgress gắn với thời gian thực của ask', () => {
  it('tiến triển qua 4 bước theo thời gian chờ của ask và hỗ trợ câu hỏi chứa từ khoá "lỗi"', async () => {
    vi.useFakeTimers()
    const client = new MockClient({ delayMs: 0, askDelayMs: 4000 })

    expect(await client.getAskProgress('DEMO-02')).toEqual({
      dang_chay: false,
      cac_buoc: [],
      da_chay_ms: null,
    })

    const askPromise = client.ask('DEMO-02', { cau_hoi: 'Vì sao cần chỉnh liều?', lich_su: [] })

    const p0 = await client.getAskProgress('DEMO-02')
    expect(p0.dang_chay).toBe(true)
    expect(p0.cac_buoc.map((b) => [b.ma, b.trang_thai])).toEqual([
      ['chuan_bi', 'dang_chay'],
      ['truy_xuat', 'cho'],
      ['goi_mo_hinh', 'cho'],
      ['kiem_chung', 'cho'],
    ])

    await vi.advanceTimersByTimeAsync(1000)
    const p1 = await client.getAskProgress('DEMO-02')
    expect(p1.cac_buoc.map((b) => [b.ma, b.trang_thai])).toEqual([
      ['chuan_bi', 'xong'],
      ['truy_xuat', 'dang_chay'],
      ['goi_mo_hinh', 'cho'],
      ['kiem_chung', 'cho'],
    ])

    await vi.advanceTimersByTimeAsync(1500)
    const p2 = await client.getAskProgress('DEMO-02')
    expect(p2.cac_buoc.map((b) => [b.ma, b.trang_thai])).toEqual([
      ['chuan_bi', 'xong'],
      ['truy_xuat', 'xong'],
      ['goi_mo_hinh', 'dang_chay'],
      ['kiem_chung', 'cho'],
    ])
    expect(p2.cac_buoc[1].nguon).toHaveLength(2)

    await vi.advanceTimersByTimeAsync(1000)
    const p3 = await client.getAskProgress('DEMO-02')
    expect(p3.cac_buoc[3].trang_thai).toBe('dang_chay')

    await vi.advanceTimersByTimeAsync(500)
    const reply = await askPromise
    expect(reply.trang_thai).toBe('ok')

    const pDone = await client.getAskProgress('DEMO-02')
    expect(pDone.dang_chay).toBe(false)
    expect(pDone.cac_buoc.every((b) => b.trang_thai === 'xong')).toBe(true)

    const globalAsk = client.ask('__global__', { cau_hoi: 'Tóm tắt lỗi ca nặng', lich_su: [] })
    const pGlobal = await client.getAskProgress('__global__')
    expect(pGlobal.cac_buoc[0].ten).toBe('Tổng hợp danh sách y lệnh')

    await vi.advanceTimersByTimeAsync(4000)
    const globalErrReply = await globalAsk
    expect(globalErrReply.trang_thai).toBe('loi')
    const pGlobalErr = await client.getAskProgress('__global__')
    expect(pGlobalErr.dang_chay).toBe(false)
    expect(pGlobalErr.cac_buoc[2].trang_thai).toBe('loi')
    expect(pGlobalErr.cac_buoc[2].ly_do).toBeTruthy()
    expect(pGlobalErr.cac_buoc[2].goi_y).toBeTruthy()
    expect(pGlobalErr.cac_buoc[3].trang_thai).toBe('bo_qua')
  })
})

describe('AssistantPanel hiển thị tiến trình hỏi đáp', () => {
  it('giữ dòng chữ cũ khi đang gửi nhưng chưa có bước nào, và hiện danh sách bước khi có cacBuoc', () => {
    const emptySendingHtml = renderAssistant({
      sending: true,
      askProgress: { cacBuoc: [], daChayMs: null },
    })
    expect(emptySendingHtml).toContain('Đang tra cứu dữ liệu và nguồn…')
    expect(emptySendingHtml).toContain('motion-safe:animate-spin')
    expect(emptySendingHtml).not.toMatch(/class="[^"]*\sanimate-spin(\s|")/)

    const liveHtml = renderAssistant({
      sending: true,
      askProgress: { cacBuoc: SAMPLE_ASK_STEPS_RUNNING, daChayMs: 1350 },
    })
    expect(liveHtml).not.toContain('Đang tra cứu dữ liệu và nguồn…')
    expect(liveHtml).toContain('Chuẩn bị ngữ cảnh ca')
    expect(liveHtml).toContain('(xong)')
    expect(liveHtml).toContain('Tra cứu nguồn')
    expect(liveHtml).toContain('openFDA')
    expect(liveHtml).toContain('Soạn câu trả lời')
    expect(liveHtml).toContain('(đang chạy)')
    expect(liveHtml).toContain('Kiểm chứng trích dẫn và số liệu')
    expect(liveHtml).toContain('(chờ)')
    expect(liveHtml).toContain('motion-safe:animate-spin')
    expect(liveHtml).not.toMatch(/class="[^"]*\sanimate-spin(\s|")/)

    const liveMatch = /aria-live="polite"[^>]*>([^<]*)<\/div>/.exec(liveHtml)
    expect(liveMatch).not.toBeNull()
    expect(liveMatch?.[1]).toBe('Bước Soạn câu trả lời: đang chạy')
    expect(liveMatch?.[1]).not.toMatch(/\d+s/)
  })

  it('gắn nút Xem các bước mặc định thu gọn dưới tin nhắn trả lời và mở được danh sách bước', () => {
    const messages: ChatMessage[] = [
      { id: 'u-1', vai: 'nguoi_dung', noi_dung: 'Vì sao chỉnh liều?' },
      {
        id: 'a-1',
        vai: 'he_thong',
        tra_loi: {
          trang_thai: 'ok',
          noi_dung: 'Cần chỉnh liều theo CrCl.',
          trich_dan: [],
          cong_cu_da_goi: ['bo_luat'],
        },
        cac_buoc: SAMPLE_ASK_STEPS_DONE,
        da_chay_ms: 1800,
      },
      {
        id: 'a-legacy',
        vai: 'he_thong',
        tra_loi: {
          trang_thai: 'ok',
          noi_dung: 'Tin nhắn lịch sử không có bước.',
          trich_dan: [],
          cong_cu_da_goi: [],
        },
      },
    ]

    const collapsedHtml = renderAssistant({ messages })
    expect(collapsedHtml).toContain('Xem các bước (4)')
    expect(collapsedHtml).toContain('aria-expanded="false"')
    expect(collapsedHtml).toContain('aria-controls=')
    expect(collapsedHtml).not.toContain('Kiểm chứng trích dẫn và số liệu')

    const expandedHtml = renderToStaticMarkup(
      <AssistantMessageSteps steps={SAMPLE_ASK_STEPS_DONE} defaultExpanded />,
    )
    expect(expandedHtml).toContain('Ẩn các bước')
    expect(expandedHtml).toContain('aria-expanded="true"')
    expect(expandedHtml).toContain('Kiểm chứng trích dẫn và số liệu')
    expect(expandedHtml).toContain('kiểm chứng đạt')
  })

  it('hiển thị lý do và gợi ý của bước lỗi trong khung chat cùng nút Gửi lại và thoát HTML thành văn bản thuần', () => {
    const xssSteps: BuocAI[] = [
      {
        ...SAMPLE_ASK_STEPS_ERROR[2],
        ten: 'Soạn câu trả lời <script>alert(1)</script>',
        ly_do: 'Lỗi <img src=x onerror=alert(1)>',
        goi_y: 'Gợi ý <script>bad()</script>',
      },
      SAMPLE_ASK_STEPS_ERROR[3],
    ]
    const messages: ChatMessage[] = [
      { id: 'u-1', vai: 'nguoi_dung', noi_dung: 'Câu hỏi gây lỗi' },
      {
        id: 'a-err',
        vai: 'he_thong',
        tra_loi: {
          trang_thai: 'loi',
          noi_dung: 'Không hoàn tất xử lý câu hỏi.',
          trich_dan: [],
          cong_cu_da_goi: [],
        },
        cac_buoc: xssSteps,
        da_chay_ms: 1500,
      },
    ]

    const html = renderAssistant({ messages, lastStatus: 'loi' })
    expect(html).toContain('role="alert"')
    expect(html).toContain('Gửi lại')
    expect(html).toContain('Xem các bước (2)')
    expect(html).not.toContain('<script>')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(html).toContain('&lt;script&gt;bad()&lt;/script&gt;')
  })
})
