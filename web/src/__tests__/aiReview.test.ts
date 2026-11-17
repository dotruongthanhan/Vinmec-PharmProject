import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError } from '../api/client.ts'
import type { FetchLike } from '../api/client.ts'
import { MockClient } from '../api/mock.ts'
import { MOCK_CASE_DETAILS } from '../api/mockData.ts'
import type { DoanNguon, KetQuaAI } from '../api/types.ts'
import {
  countAiSummary,
  getSafeHttpsUrl,
  mergeFindingsFeedback,
  selectFindingsSource,
  splitHighlightSegments,
} from '../lib/aiReview.ts'

describe('ApiClient các điểm cuối AI và nguồn tài liệu', () => {
  it('getAi trả về null khi gặp 404 mã chua_chay', async () => {
    const fakeFetch: FetchLike = async () =>
      new Response(
        JSON.stringify({
          loi: { ma: 'chua_chay', thong_bao: 'Chưa chạy phân tích AI cho ca này.' },
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      )

    const client = new ApiClient('/api', fakeFetch)
    const result = await client.getAi('DEMO-02')
    expect(result).toBeNull()
  })

  it('getAi ném ApiError khi gặp 404 khác mã chua_chay', async () => {
    const fakeFetch: FetchLike = async () =>
      new Response(
        JSON.stringify({
          loi: { ma: 'khong_tim_thay', thong_bao: 'Không tìm thấy ca DEMO-99.' },
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      )

    const client = new ApiClient('/api', fakeFetch)
    await expect(client.getAi('DEMO-99')).rejects.toBeInstanceOf(ApiError)
    await expect(client.getAi('DEMO-99')).rejects.toMatchObject({
      ma: 'khong_tim_thay',
      status: 404,
    })
  })

  it('startAi gửi đúng đường dẫn, phương thức POST và cờ chay_lai', async () => {
    const captured: { url: string; method: string; body: string }[] = []
    const sample: KetQuaAI = {
      trang_thai: 'dang_chay',
      nhan_dinh: null,
      canh_bao: [],
      thoi_gian_ms: null,
      mo_hinh: null,
    }

    const fakeFetch: FetchLike = async (input, init) => {
      captured.push({
        url: String(input),
        method: init?.method ?? '',
        body: typeof init?.body === 'string' ? init.body : '',
      })
      return new Response(JSON.stringify(sample), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const client = new ApiClient('/api', fakeFetch)
    await client.startAi('DEMO-02')
    await client.startAi('DEMO-02', true)

    expect(captured).toHaveLength(2)
    expect(captured[0].url).toBe('/api/cases/DEMO-02/ai')
    expect(captured[0].method).toBe('POST')
    expect(JSON.parse(captured[0].body)).toEqual({ chay_lai: false })

    expect(captured[1].url).toBe('/api/cases/DEMO-02/ai')
    expect(captured[1].method).toBe('POST')
    expect(JSON.parse(captured[1].body)).toEqual({ chay_lai: true })
  })

  it('getSource gọi đúng đường dẫn và mã hoá ký tự đặc biệt như dấu gạch đứng', async () => {
    let capturedUrl = ''
    const sampleSource: DoanNguon = {
      doan_trich_id: 'fda_merrem|renal_01',
      nguon_nhan: 'Nhãn FDA MERREM IV',
      duong_dan_muc: 'Dosage and Administration',
      tang_tin_cay: 3,
      phien_ban: '2025',
      url_goc: null,
      noi_dung: 'Dosage adjustment is recommended.',
    }

    const fakeFetch: FetchLike = async (input) => {
      capturedUrl = String(input)
      return new Response(JSON.stringify(sampleSource), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const client = new ApiClient('/api', fakeFetch)
    const result = await client.getSource('DEMO-02', 'fda_merrem|renal_01')

    expect(capturedUrl).toBe('/api/cases/DEMO-02/sources/fda_merrem%7Crenal_01')
    expect(result).toEqual(sampleSource)
  })
})

describe('các hàm thuần cho luồng AI nền', () => {
  it('selectFindingsSource chọn đúng bảng AI hoặc bảng luật theo trạng thái', () => {
    const ruleTable = MOCK_CASE_DETAILS['DEMO-02'].nhan_dinh
    const aiTable = {
      can_chu_y: [
        {
          ...ruleTable.can_chu_y[0],
          dien_giai_ai: 'Diễn giải kiểm thử',
        },
      ],
      dat: ruleTable.dat,
    }
    const aiDone: KetQuaAI = {
      trang_thai: 'xong',
      nhan_dinh: aiTable,
      canh_bao: [],
      thoi_gian_ms: 3000,
      mo_hinh: 'mock-ai',
    }
    const aiDoneEmpty: KetQuaAI = {
      trang_thai: 'xong',
      nhan_dinh: null,
      canh_bao: [],
      thoi_gian_ms: 3000,
      mo_hinh: 'mock-ai',
    }

    expect(selectFindingsSource(ruleTable, 'xong', aiDone)).toBe(aiTable)
    expect(selectFindingsSource(ruleTable, 'dang_chay', aiDone)).toBe(ruleTable)
    expect(selectFindingsSource(ruleTable, 'loi', aiDone)).toBe(ruleTable)
    expect(selectFindingsSource(ruleTable, 'tat', aiDone)).toBe(ruleTable)
    expect(selectFindingsSource(ruleTable, 'xong', aiDoneEmpty)).toBe(ruleTable)
  })

  it('mergeFindingsFeedback giữ trạng thái đã phản hồi theo nhan_dinh_id khi chuyển nguồn', () => {
    const ruleTable = MOCK_CASE_DETAILS['DEMO-02'].nhan_dinh
    const recorded = {
      phan_hoi: 'dong_y' as const,
      phan_hoi_nhan: 'Đồng ý',
      nhom_ly_do: null,
      ly_do: null,
      thoi_diem_text: '16/11/2026 14:00',
    }
    const ruleWithFeedback = {
      ...ruleTable,
      can_chu_y: [{ ...ruleTable.can_chu_y[0], phan_hoi: recorded }],
    }
    const aiWithoutFeedback = {
      can_chu_y: [{ ...ruleTable.can_chu_y[0], phan_hoi: null, dien_giai_ai: 'Diễn giải' }],
      dat: ruleTable.dat,
    }

    const merged = mergeFindingsFeedback(aiWithoutFeedback, {}, [ruleWithFeedback])
    expect(merged.can_chu_y[0].phan_hoi).toEqual(recorded)
  })

  it('countAiSummary đếm đúng 1 nhận định có diễn giải và 1 nhận định do AI thêm cho DEMO-02', async () => {
    vi.useFakeTimers()
    try {
      const client = new MockClient({ delayMs: 0 })
      await client.startAi('DEMO-02')
      vi.advanceTimersByTime(3000)
      const done = await client.getAi('DEMO-02')

      expect(done?.trang_thai).toBe('xong')
      expect(countAiSummary(done)).toEqual({ coDienGiai: 1, doAiThem: 1 })
    } finally {
      vi.useRealTimers()
    }
  })

  it('splitHighlightSegments tách đúng 3 phần khi tìm thấy và 1 phần khi không thấy hoặc rỗng', () => {
    const content = 'Phần mở đầu. Đoạn trích dẫn cần tô nền. Phần kết thúc.'

    const found = splitHighlightSegments(content, 'Đoạn trích dẫn cần tô nền.')
    expect(found).toHaveLength(3)
    expect(found).toEqual([
      { text: 'Phần mở đầu. ', highlighted: false },
      { text: 'Đoạn trích dẫn cần tô nền.', highlighted: true },
      { text: ' Phần kết thúc.', highlighted: false },
    ])

    const notFound = splitHighlightSegments(content, 'Không tồn tại trong văn bản')
    expect(notFound).toHaveLength(1)
    expect(notFound).toEqual([{ text: content, highlighted: false }])

    const emptyQuote = splitHighlightSegments(content, '')
    expect(emptyQuote).toHaveLength(1)
    expect(emptyQuote).toEqual([{ text: content, highlighted: false }])
  })

  it('getSafeHttpsUrl chỉ chấp nhận địa chỉ HTTPS hợp lệ', () => {
    const httpsPrefix = ['ht', 'tps://'].join('')
    const httpPrefix = ['ht', 'tp://'].join('')

    expect(getSafeHttpsUrl(`${httpsPrefix}example.org/doc`)).toBe(`${httpsPrefix}example.org/doc`)
    expect(getSafeHttpsUrl(`${httpPrefix}example.org/doc`)).toBeNull()
    expect(getSafeHttpsUrl('javascript:alert(1)')).toBeNull()
    expect(getSafeHttpsUrl(null)).toBeNull()
  })
})

describe('MockClient luồng AI giả lập', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('startAi trả dang_chay và sau thời gian giả getAi trả xong; mọi dòng luật DEMO-02 khớp chi tiết ca', async () => {
    vi.useFakeTimers()
    const client = new MockClient({ delayMs: 0 })

    expect(await client.getAi('DEMO-02')).toBeNull()

    const started = await client.startAi('DEMO-02')
    expect(started.trang_thai).toBe('dang_chay')

    const midPoll = await client.getAi('DEMO-02')
    expect(midPoll?.trang_thai).toBe('dang_chay')

    vi.advanceTimersByTime(3000)

    const finished = await client.getAi('DEMO-02')
    expect(finished?.trang_thai).toBe('xong')
    expect(finished?.nhan_dinh).not.toBeNull()

    const ruleDetail = MOCK_CASE_DETAILS['DEMO-02'].nhan_dinh
    const ruleDetailMap = new Map(
      [...ruleDetail.can_chu_y, ...ruleDetail.dat].map((item) => [item.nhan_dinh_id, item]),
    )

    const aiItems = [
      ...(finished?.nhan_dinh?.can_chu_y ?? []),
      ...(finished?.nhan_dinh?.dat ?? []),
    ]
    const aiRuleItems = aiItems.filter((item) => item.nguon_goc_ma === 'luat')
    expect(aiRuleItems).toHaveLength(ruleDetailMap.size)

    for (const item of aiRuleItems) {
      const expected = ruleDetailMap.get(item.nhan_dinh_id)
      expect(expected).toBeDefined()
      expect(item.ket_luan_ma).toBe(expected?.ket_luan_ma)
      expect(item.muc_do_ma).toBe(expected?.muc_do_ma)
    }

    const demo02RuleWithAi = aiRuleItems.find(
      (item) => item.nhan_dinh_id === 'lieu_than_can_chinh|CT-DEMO02-01',
    )
    expect(demo02RuleWithAi?.dien_giai_ai).toBeTruthy()
    expect(demo02RuleWithAi?.de_xuat_ai).toBeTruthy()
    expect(demo02RuleWithAi?.trich_dan).toHaveLength(1)

    const demo02Added = aiItems.filter((item) => item.nhan_dinh_id.startsWith('ai|'))
    expect(demo02Added).toHaveLength(1)
    expect(demo02Added[0].yeu_to).toMatch(/^3\./)
    expect(demo02Added[0].ket_luan_ma).toBe('khong_du_du_lieu')
    expect(demo02Added[0].nguon_goc_ma).toBe('ai_da_kiem_chung')
    expect(demo02Added[0].ma_luat).toBeNull()

    const sourceId = demo02RuleWithAi?.trich_dan[0].doan_trich_id ?? ''
    const sourceDoc = await client.getSource('DEMO-02', sourceId)
    expect(sourceDoc.noi_dung).toContain(demo02RuleWithAi?.trich_dan[0].trich_nguyen_van ?? '')

    const fb = await client.sendFeedback('DEMO-02', {
      nhan_dinh_id: demo02Added[0].nhan_dinh_id,
      phan_hoi: 'dong_y',
      nhom_ly_do: null,
      ly_do: null,
    })
    expect(fb.phan_hoi).toBe('dong_y')
  })

  it('DEMO-06 có nhận định AI về đoạn văn bản bất thường và ca khác xong không thêm dòng', async () => {
    vi.useFakeTimers()
    const client = new MockClient({ delayMs: 0 })

    await client.startAi('DEMO-06')
    await client.startAi('DEMO-05')
    vi.advanceTimersByTime(3000)

    const demo06 = await client.getAi('DEMO-06')
    expect(demo06?.trang_thai).toBe('xong')
    const demo06AiRows = (demo06?.nhan_dinh?.can_chu_y ?? []).filter((item) =>
      item.nhan_dinh_id.startsWith('ai|'),
    )
    expect(demo06AiRows).toHaveLength(1)
    expect(demo06AiRows[0].nhan_xet).toBe(
      'Bệnh án có đoạn văn bản bất thường, giống chỉ thị cho hệ thống',
    )

    const demo05 = await client.getAi('DEMO-05')
    expect(demo05?.trang_thai).toBe('xong')
    expect(demo05?.nhan_dinh?.can_chu_y).toHaveLength(
      MOCK_CASE_DETAILS['DEMO-05'].nhan_dinh.can_chu_y.length,
    )
    expect(demo05?.nhan_dinh?.dat).toHaveLength(
      MOCK_CASE_DETAILS['DEMO-05'].nhan_dinh.dat.length,
    )
  })
})
