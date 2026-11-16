import { describe, expect, it } from 'vitest'
import { ApiClient, ApiError } from '../api/client.ts'
import type { FetchLike } from '../api/client.ts'
import { MockClient } from '../api/mock.ts'
import { MOCK_CASE_DETAILS, MOCK_CASES } from '../api/mockData.ts'
import type { PhanHoiDaGhi } from '../api/types.ts'

describe('ApiClient', () => {
  it('trả về dữ liệu khi phản hồi HTTP 200 hợp lệ', async () => {
    const calls: string[] = []
    const fakeFetch: FetchLike = async (input) => {
      calls.push(String(input))
      return new Response(JSON.stringify(MOCK_CASES), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const client = new ApiClient('/api', fakeFetch)
    const result = await client.getCases()
    expect(calls).toEqual(['/api/cases'])
    expect(result.cases).toHaveLength(6)
  })

  it('ném ApiError giữ nguyên ma và status khi 404 trả JSON có loi', async () => {
    const fakeFetch: FetchLike = async () =>
      new Response(
        JSON.stringify({
          loi: { ma: 'khong_tim_thay', thong_bao: 'Không thấy ca DEMO-99' },
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      )

    const client = new ApiClient('/api', fakeFetch)
    await expect(client.getCase('DEMO-99')).rejects.toMatchObject({
      name: 'ApiError',
      ma: 'khong_tim_thay',
      thong_bao: 'Không thấy ca DEMO-99',
      status: 404,
    })
  })

  it('ném ApiError với ma loi_he_thong khi thân lỗi không phải JSON', async () => {
    const fakeFetch: FetchLike = async () =>
      new Response('Bad Gateway', {
        status: 502,
        headers: { 'Content-Type': 'text/plain' },
      })

    const client = new ApiClient('/api', fakeFetch)
    try {
      await client.getCases()
      expect.fail('Phải ném ApiError')
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError)
      const apiErr = err as ApiError
      expect(apiErr.ma).toBe('loi_he_thong')
      expect(apiErr.status).toBe(502)
    }
  })

  it('sendFeedback gửi đúng phương thức POST, đường dẫn và thân JSON', async () => {
    let capturedUrl = ''
    let capturedMethod = ''
    let capturedBody = ''
    const recorded: PhanHoiDaGhi = {
      phan_hoi: 'bac_bo',
      phan_hoi_nhan: 'Bác bỏ',
      nhom_ly_do: 'Không phù hợp lâm sàng',
      ly_do: 'Đã hội chẩn',
      thoi_diem_text: '16/11/2026 10:32',
    }

    const fakeFetch: FetchLike = async (input, init) => {
      capturedUrl = String(input)
      capturedMethod = init?.method ?? ''
      capturedBody = typeof init?.body === 'string' ? init.body : ''
      return new Response(JSON.stringify(recorded), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const client = new ApiClient('/api', fakeFetch)
    const response = await client.sendFeedback('DEMO-02', {
      nhan_dinh_id: 'lieu_than_can_chinh|CT-DEMO02-01',
      phan_hoi: 'bac_bo',
      nhom_ly_do: 'Không phù hợp lâm sàng',
      ly_do: 'Đã hội chẩn',
    })

    expect(capturedUrl).toBe('/api/cases/DEMO-02/feedback')
    expect(capturedMethod).toBe('POST')
    expect(JSON.parse(capturedBody)).toEqual({
      nhan_dinh_id: 'lieu_than_can_chinh|CT-DEMO02-01',
      phan_hoi: 'bac_bo',
      nhom_ly_do: 'Không phù hợp lâm sàng',
      ly_do: 'Đã hội chẩn',
    })
    expect(response).toEqual(recorded)
  })
})

describe('dữ liệu mẫu và MockClient', () => {
  it('mỗi ChiTietCa có đúng 4 chỉ số và nhan_dinh_id duy nhất trong ca', () => {
    const entries = Object.values(MOCK_CASE_DETAILS)
    expect(entries.length).toBeGreaterThanOrEqual(3)

    for (const detail of entries) {
      expect(detail.chi_so.map((c) => c.cong_thuc)).toEqual([
        'cockcroft_gault',
        'egfr_ckd_epi_2021',
        'bmi',
        'bsa_mosteller',
      ])

      const ids = [
        ...detail.nhan_dinh.can_chu_y.map((n) => n.nhan_dinh_id),
        ...detail.nhan_dinh.dat.map((n) => n.nhan_dinh_id),
      ]
      expect(new Set(ids).size).toBe(ids.length)
    }
  })

  it('MockClient.getCase xử lý đúng ca có và không có chi tiết', async () => {
    const partialClient = new MockClient({
      delayMs: 0,
      cases: MOCK_CASES,
      details: { 'DEMO-02': MOCK_CASE_DETAILS['DEMO-02'] },
    })

    for (const row of MOCK_CASES.cases) {
      if (row.ca_id === 'DEMO-02') {
        const detail = await partialClient.getCase(row.ca_id)
        expect(detail.ca_id).toBe('DEMO-02')
      } else {
        await expect(partialClient.getCase(row.ca_id)).rejects.toMatchObject({
          name: 'ApiError',
          ma: 'khong_tim_thay',
          status: 404,
        })
      }
    }
  })

  it('MockClient ghi phản hồi, cập nhật da_phan_hoi_het và trả chua_san_sang cho ask', async () => {
    const client = new MockClient({ delayMs: 0 })
    const fb = await client.sendFeedback('DEMO-02', {
      nhan_dinh_id: 'lieu_than_can_chinh|CT-DEMO02-01',
      phan_hoi: 'dong_y',
      nhom_ly_do: null,
      ly_do: null,
    })
    expect(fb.phan_hoi).toBe('dong_y')

    const queue = await client.getCases()
    const row = queue.cases.find((c) => c.ca_id === 'DEMO-02')
    expect(row?.da_phan_hoi_het).toBe(true)

    const reply = await client.ask('DEMO-02', { cau_hoi: 'Vì sao chỉnh liều?', lich_su: [] })
    expect(reply.trang_thai).toBe('chua_san_sang')
  })
})
