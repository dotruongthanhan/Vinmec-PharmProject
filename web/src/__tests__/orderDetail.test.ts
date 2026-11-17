import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData.ts'
import {
  computeSixFactorsStatus,
  stripPendingSourceNote,
} from '../lib/orderDetail.ts'

describe('trạng thái sáu yếu tố thẩm định', () => {
  it('yếu tố không có luật luôn trả về chua_co_luat, không bao giờ ra dat', () => {
    const demo02Factors = computeSixFactorsStatus(MOCK_CASE_DETAILS['DEMO-02'].nhan_dinh)
    expect(demo02Factors.map((f) => [f.index, f.status])).toEqual([
      [1, 'dat'],
      [2, 'dat'],
      [3, 'chua_co_luat'],
      [4, 'chua_co_luat'],
      [5, 'chua_co_luat'],
      [6, 'co_van_de'],
    ])

    const emptyFactors = computeSixFactorsStatus({
      can_chu_y: [],
      dat: [],
      yeu_to_chua_kiem: [],
    })
    expect(emptyFactors.every((f) => f.status === 'chua_co_luat')).toBe(true)
    expect(emptyFactors.some((f) => f.status === 'dat')).toBe(false)
  })

  it('nhận diện đúng yếu tố thiếu dữ liệu trên DEMO-03', () => {
    const demo03Factors = computeSixFactorsStatus(MOCK_CASE_DETAILS['DEMO-03'].nhan_dinh)
    expect(demo03Factors[0].status).toBe('thieu_du_lieu')
    expect(demo03Factors[1].status).toBe('dat')
    expect(demo03Factors[2].status).toBe('chua_co_luat')
  })

  it('bỏ câu chờ kho tri thức khi thẻ nhận định đã có trích dẫn nguồn', () => {
    const note = 'Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức. (Dòng luật chưa được dược sĩ duyệt)'
    expect(stripPendingSourceNote(note, true)).toBe('(Dòng luật chưa được dược sĩ duyệt)')
    expect(stripPendingSourceNote(note, false)).toBe(note)
  })
})
