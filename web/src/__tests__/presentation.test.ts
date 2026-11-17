import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData.ts'
import type { DiUngMa, KetLuanMa, MucDoMa, NhanDinh } from '../api/types.ts'
import {
  findMetricByFormula,
  getChatStatusPresentation,
  inferMetricFromCitation,
  parseCitationsInText,
  sortAttentionFindings,
} from '../lib/presentation.ts'
import {
  ICON_OF_TONE,
  iconOfAllergy,
  toneOfAllergy,
  toneOfFinding,
} from '../lib/severity.ts'

describe('kiểu hiển thị theo mã qua severity.ts', () => {
  it('mỗi muc_do_ma với can_xem trả về tông màu và biểu tượng tương ứng', () => {
    const codes: MucDoMa[] = ['nghiem_trong', 'can_luu_y', null]
    const tones = codes.map((muc_do_ma) =>
      toneOfFinding({ ket_luan_ma: 'can_xem', muc_do_ma }),
    )
    expect(tones).toEqual(['danger', 'warning', 'warning'])
    expect(new Set(tones.map((t) => ICON_OF_TONE[t])).size).toBe(2)
  })

  it('mỗi ket_luan_ma trả về một tông nghĩa và biểu tượng lucide khác nhau', () => {
    const codes: KetLuanMa[] = ['dat', 'can_xem', 'khong_du_du_lieu', 'ngoai_hdsd']
    const tones = codes.map((ket_luan_ma) =>
      toneOfFinding({
        ket_luan_ma,
        muc_do_ma: ket_luan_ma === 'can_xem' ? 'nghiem_trong' : null,
      }),
    )
    const icons = tones.map((t) => ICON_OF_TONE[t])
    expect(new Set(tones).size).toBe(4)
    expect(new Set(icons).size).toBe(4)
  })

  it('ba trạng thái dị ứng trả về ba tông và biểu tượng khác nhau', () => {
    const codes: DiUngMa[] = ['co_di_ung', 'khong_di_ung_da_hoi', 'chua_co_thong_tin']
    const tones = codes.map((c) => toneOfAllergy(c))
    const icons = codes.map((c) => iconOfAllergy(c))
    expect(new Set(tones).size).toBe(3)
    expect(new Set(icons).size).toBe(3)
  })
})

describe('findMetricByFormula và các hàm hỗ trợ hiển thị', () => {
  it('tìm đúng ChiSo theo cong_thuc và trả undefined nếu không có', () => {
    const chiSo = MOCK_CASE_DETAILS['DEMO-02'].chi_so
    expect(findMetricByFormula(chiSo, 'cockcroft_gault')?.gia_tri_text).toBe('16,0')
    expect(findMetricByFormula(chiSo, 'bsa_mosteller')?.gia_tri_text).toBe('1,47')
    expect(findMetricByFormula(chiSo, 'khong_ton_tai')).toBeUndefined()
    expect(findMetricByFormula(chiSo, null)).toBeUndefined()
    expect(findMetricByFormula(chiSo, undefined)).toBeUndefined()
  })

  it('suy tìm đúng ChiSo từ trích dẫn tính toán theo mã hoặc tên chỉ số', () => {
    const chiSo = MOCK_CASE_DETAILS['DEMO-02'].chi_so
    expect(inferMetricFromCitation(chiSo, 'cockcroft_gault', '')?.cong_thuc).toBe(
      'cockcroft_gault',
    )
    expect(inferMetricFromCitation(chiSo, null, 'Chỉ số CrCl ước tính')?.cong_thuc).toBe(
      'cockcroft_gault',
    )
    expect(inferMetricFromCitation(chiSo, null, 'eGFR CKD-EPI')?.cong_thuc).toBe(
      'egfr_ckd_epi_2021',
    )
    expect(inferMetricFromCitation(chiSo, null, 'BSA Mosteller')?.cong_thuc).toBe(
      'bsa_mosteller',
    )
    expect(inferMetricFromCitation(chiSo, null, 'Không khớp')).toBeUndefined()
  })

  it('đặt nhận định AI chưa kiểm chứng dưới mọi nhận định đã kiểm chứng', () => {
    const base = MOCK_CASE_DETAILS['DEMO-02'].nhan_dinh.can_chu_y[0]
    const list: NhanDinh[] = [
      { ...base, nhan_dinh_id: 'ai-1', nguon_goc_ma: 'ai_chua_kiem_chung' },
      { ...base, nhan_dinh_id: 'luat-1', nguon_goc_ma: 'luat' },
      { ...base, nhan_dinh_id: 'ai-ok', nguon_goc_ma: 'ai_da_kiem_chung' },
    ]
    expect(sortAttentionFindings(list).map((item) => item.nhan_dinh_id)).toEqual([
      'luat-1',
      'ai-ok',
      'ai-1',
    ])
  })

  it('tách trích dẫn [n] an toàn khỏi chuỗi câu trả lời', () => {
    const segments = parseCitationsInText('Xem creatinin [1] và liều thận [2].', [
      { so: 1, loai_ma: 'du_lieu', nhan: 'Creatinin máu', ban_ghi_id: 'XN-DEMO02-01' },
    ])
    expect(segments).toEqual([
      { kind: 'text', value: 'Xem creatinin ' },
      {
        kind: 'citation',
        label: '[1]',
        citation: {
          so: 1,
          loai_ma: 'du_lieu',
          nhan: 'Creatinin máu',
          ban_ghi_id: 'XN-DEMO02-01',
        },
      },
      { kind: 'text', value: ' và liều thận [2].' },
    ])
  })

  it('ánh xạ đúng nhãn trạng thái câu trả lời khung hỏi thêm', () => {
    expect(getChatStatusPresentation('ok').label).toBe('Đã kiểm chứng nguồn')
    expect(getChatStatusPresentation('chua_san_sang').label).toBe(
      'Chức năng hỏi thêm chưa sẵn sàng',
    )
    expect(getChatStatusPresentation('loi').className).toBe('chat-status-loi')
  })
})
