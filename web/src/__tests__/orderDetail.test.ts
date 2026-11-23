import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData.ts'
import {
  computeSixFactorsStatus,
  countAttentionByFactor,
  factorIndexOf,
  filterTreatmentSheetNotes,
  hasSevereByFactor,
  isTreatmentSheetNote,
  parseReviewFactorParam,
  stripPendingSourceNote,
  updateReviewFactorParams,
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
      [7, 'dat'],
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

  it('lọc đúng phiếu điều trị từ danh sách diễn biến mà không tự tạo bản ghi giả', () => {
    const demo02Notes = MOCK_CASE_DETAILS['DEMO-02'].chi_tiet.dien_bien
    const demo06Notes = MOCK_CASE_DETAILS['DEMO-06'].chi_tiet.dien_bien
    expect(filterTreatmentSheetNotes(demo02Notes)).toHaveLength(1)
    expect(filterTreatmentSheetNotes(demo06Notes)).toHaveLength(0)
    expect(isTreatmentSheetNote({ loai_nhan: 'Phiếu điều trị' })).toBe(true)
    expect(isTreatmentSheetNote({ loai_nhan: 'Phiếu khám' })).toBe(false)
  })

  it('factorIndexOf trích chỉ số yếu tố từ chuỗi đầu mục và trả null khi lạ', () => {
    expect(factorIndexOf('3. Chỉ định, liều, đường dùng')).toBe(3)
    expect(factorIndexOf('6 · Cơ địa và xét nghiệm')).toBe(6)
    expect(factorIndexOf(' 1. Dị ứng, quá mẫn')).toBe(1)
    expect(factorIndexOf('chuỗi lạ')).toBeNull()
    expect(factorIndexOf('')).toBeNull()
    expect(factorIndexOf('10. Ngoài phạm vi')).toBeNull()
  })

  it('đếm số nhận định cần chú ý và cờ mức nghiêm trọng theo từng yếu tố', () => {
    const demo02CanChuY = MOCK_CASE_DETAILS['DEMO-02'].nhan_dinh.can_chu_y
    expect(countAttentionByFactor(demo02CanChuY)).toEqual({
      1: 0,
      2: 0,
      3: 0,
      4: 0,
      5: 0,
      6: 1,
      7: 0,
    })
    expect(hasSevereByFactor(demo02CanChuY)).toEqual({
      1: false,
      2: false,
      3: false,
      4: false,
      5: false,
      6: true,
      7: false,
    })

    const demo05CanChuY = MOCK_CASE_DETAILS['DEMO-05'].nhan_dinh.can_chu_y
    expect(countAttentionByFactor(demo05CanChuY)).toEqual({
      1: 0,
      2: 0,
      3: 0,
      4: 0,
      5: 0,
      6: 0,
      7: 1,
    })
    expect(hasSevereByFactor(demo05CanChuY)[7]).toBe(false)
  })

  it('đọc và cập nhật tham số URL yt hợp lệ, giữ nguyên các tham số khác', () => {
    expect(parseReviewFactorParam(null)).toBe('tong_quan')
    expect(parseReviewFactorParam('')).toBe('tong_quan')
    expect(parseReviewFactorParam('tong_quan')).toBe('tong_quan')
    expect(parseReviewFactorParam('1')).toBe(1)
    expect(parseReviewFactorParam('7')).toBe(7)
    expect(parseReviewFactorParam('0')).toBe('tong_quan')
    expect(parseReviewFactorParam('8')).toBe('tong_quan')
    expect(parseReviewFactorParam('abc')).toBe('tong_quan')

    const pFactor = updateReviewFactorParams(new URLSearchParams('tab=tham_dinh&yl=YL-01'), 6)
    expect(pFactor.get('tab')).toBe('tham_dinh')
    expect(pFactor.get('yl')).toBe('YL-01')
    expect(pFactor.get('yt')).toBe('6')

    const pOverview = updateReviewFactorParams(pFactor, 'tong_quan')
    expect(pOverview.get('tab')).toBe('tham_dinh')
    expect(pOverview.get('yl')).toBe('YL-01')
    expect(pOverview.has('yt')).toBe(false)
  })
})
