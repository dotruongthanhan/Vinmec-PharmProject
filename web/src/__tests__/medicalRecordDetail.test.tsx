import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { ChiTietCa, MedicalOrder, TreatmentSheet } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'
import { OrderChoices, SelectedOrderDetails, TreatmentSheets } from '../features/order-detail/MedicalRecordSections'
import { orderSelectionParams, selectMedicalOrder } from '../lib/medicalRecord'
import { formatClinicalText } from '../lib/displayFormat'

const old: MedicalOrder = {
  y_lenh_id: 'YL-CU', dot_dieu_tri_id: 'DT-CU', thu_tu_dot: 1,
  thoi_diem_ke: '2026-11-01T08:00:00+07:00', trang_thai: 'ngung',
  khoa_ke_don: 'Khoa cũ giả lập', luong_duyet: 'hau_kiem', ly_do_ngung: 'Đổi y lệnh giả lập',
  thay_the_y_lenh_id: 'YL-TT', la_trong_tam: false,
  cot: ['Thuốc', 'Liều', 'Tần suất', 'Đường dùng', 'Lịch dùng'],
  dong: [{ Thuốc: 'Thuốc cũ giả lập', Liều: '10 mg', 'Tần suất': '1 lần/ngày', 'Đường dùng': 'uống', 'Lịch dùng': '01/11/2026 08:00 (10 mg)' }],
}
const focus: MedicalOrder = { ...old, y_lenh_id: 'YL-TT', dot_dieu_tri_id: 'DT-MOI', thu_tu_dot: 2,
  trang_thai: 'cho_duyet', la_trong_tam: true, dong: MOCK_CASE_DETAILS['DEMO-02'].chi_tiet.y_lenh.cho_duyet.dong }
const sheet: TreatmentSheet = {
  phieu_dieu_tri_id: 'PDT-1', dot_dieu_tri_id: 'DT-CU', thu_tu_dot: 1,
  ngay_dieu_tri: 1, thoi_diem_lap: '2026-11-01T08:30:00+07:00', vai_tro_nguoi_lap: 'bac_si_truc',
  dien_bien: 'Diễn biến giả lập', danh_gia: 'Đánh giá giả lập', huong_xu_tri: 'Xử trí giả lập',
  che_do_cham_soc: 'cấp 2', che_do_an: 'Ăn giả lập', theo_doi: ['Theo dõi giả lập'],
  dan_do: 'Dặn dò giả lập', y_lenh_trong_ngay: ['YL-CU'],
}
const detail: ChiTietCa = { ...MOCK_CASE_DETAILS['DEMO-02'], danh_sach_y_lenh: [old, focus],
  phieu_dieu_tri: [sheet, { ...sheet, phieu_dieu_tri_id: 'PDT-2', dot_dieu_tri_id: 'DT-MOI', thu_tu_dot: 2 }] }

function html(query = '?tab=y_lenh', value = detail): string {
  return renderToStaticMarkup(<TooltipProvider><MemoryRouter initialEntries={[query]}>
    <OrderDetailView detail={value} aiTrangThai="tat" aiKetQua={null} aiThoiGianMs={null}
      aiCanhBao={[]} sessionFeedbackForCase={{}} onRerunAi={() => {}}
      isFeedbackSubmitting={() => false} getFeedbackError={() => null}
      onSubmitFeedback={async () => true} onClearFeedbackError={() => {}}
      onOpenEvidence={() => {}} onAskAboutFinding={() => {}} />
  </MemoryRouter></TooltipProvider>)
}

describe('bộ chọn y lệnh trong hồ sơ', () => {
  it('đếm y lệnh thay vì dòng thuốc và mặc định chọn trọng tâm', () => {
    const rendered = html()
    expect(rendered).toContain('Y lệnh (2)')
    expect(rendered).toContain('Chi tiết y lệnh chờ duyệt')
    expect(rendered).not.toContain('Thuốc cũ giả lập</td>')
    expect(selectMedicalOrder(detail.danh_sach_y_lenh!, null)?.y_lenh_id).toBe('YL-TT')
  })
  it('URL chọn y lệnh cũ hiển thị đúng dòng và lý do ngừng, không mở thẩm định', () => {
    const rendered = html('?tab=y_lenh&yl=YL-CU')
    expect(rendered).toContain('Thuốc cũ giả lập</td>')
    expect(rendered).toContain('Khoa cũ giả lập')
    expect(rendered).toContain('Đổi y lệnh giả lập')
    expect(rendered).not.toContain('Chi tiết y lệnh chờ duyệt')
    expect(rendered).not.toContain('Bấm một dòng thuốc')
    const drugRow = rendered.match(/<tr[^>]*>\s*<td[^>]*>1<\/td>\s*<td[^>]*>Thuốc cũ giả lập<\/td>/)?.[0]
    expect(drugRow).toBeDefined()
    expect(drugRow).not.toContain('cursor-pointer')
    expect(drugRow).not.toContain('tabindex="0"')
  })
  it('tham số chọn y lệnh giữ URL và mã không hợp lệ về trọng tâm', () => {
    const params = orderSelectionParams(new URLSearchParams('tab=phieu_dieu_tri&khac=1'), 'YL CU/+')
    expect(params.get('tab')).toBe('y_lenh')
    expect(params.get('yl')).toBe('YL CU/+')
    expect(params.get('khac')).toBe('1')
    expect(selectMedicalOrder([old, focus], 'khong-co')).toBe(focus)
    expect(selectMedicalOrder([{ ...focus, y_lenh_id: 'YL-CA-KHAC' }], 'YL-CU')?.y_lenh_id).toBe('YL-CA-KHAC')
  })
  it('lựa chọn nhóm theo lần vào viện, có tên thuốc và radio dùng bàn phím', () => {
    const rendered = renderToStaticMarkup(<OrderChoices orders={[old, focus]} selectedId="YL-TT"
      detail={detail} onSelect={() => {}} />)
    expect(rendered).toContain('Lần vào viện 1')
    expect(rendered).toContain('Lần vào viện 2')
    expect(rendered).toContain('role="radiogroup"')
    expect(rendered).toContain('aria-label="Chọn y lệnh"')
    expect(rendered).toContain('Thuốc cũ giả lập')
    expect(rendered).toContain('aria-checked="true"')
  })
  it('y lệnh nền trong mock cũ không hiện nhận định của y lệnh trọng tâm', () => {
    const value = { ...old, cot: [...old.cot, 'Nhận định'],
      dong: old.dong.map((row) => ({ ...row, 'Nhận định': 'CẢNH BÁO TRỌNG TÂM' })) }
    const rendered = renderToStaticMarkup(<SelectedOrderDetails order={value} />)
    expect(rendered).not.toContain('CẢNH BÁO TRỌNG TÂM')
    expect(rendered).toContain('Chưa có thẩm định cho y lệnh này')
  })
})

describe('phiếu điều trị', () => {
  it('đếm và nhóm theo lần vào viện, đủ nội dung và liên kết chọn y lệnh', () => {
    const rendered = html('?tab=phieu_dieu_tri')
    expect(rendered).toContain('Phiếu điều trị (2)')
    for (const text of ['Lần vào viện 1', 'Lần vào viện 2', 'Ngày điều trị 1', 'Bác sĩ trực',
      'Diễn biến giả lập', 'Đánh giá giả lập', 'Xử trí giả lập', 'Theo dõi giả lập', 'Dặn dò giả lập']) {
      expect(rendered).toContain(text)
    }
    expect(rendered).toContain('tab=y_lenh&amp;yl=YL-CU')
  })
  it('mảng phiếu rỗng và không có ghi chép tờ điều trị dùng trạng thái rỗng', () => {
    const bare = { ...detail, phieu_dieu_tri: [], chi_tiet: { ...detail.chi_tiet, dien_bien: [] } }
    const rendered = html('?tab=phieu_dieu_tri', bare)
    expect(rendered).toContain('Phiếu điều trị (0)')
    expect(rendered).toContain('Chưa có phiếu điều trị')
    const empty = renderToStaticMarkup(<MemoryRouter><TreatmentSheets detail={bare} /></MemoryRouter>)
    expect(empty).toContain('Chưa có phiếu điều trị')
  })
  it('mảng phiếu rỗng quay về ghi chép tờ điều trị trong diễn biến (chế độ đọc tệp)', () => {
    const rendered = html('?tab=phieu_dieu_tri', { ...detail, phieu_dieu_tri: [] })
    expect(rendered).not.toContain('Phiếu điều trị (0)')
    expect(rendered).not.toContain('Chưa có phiếu điều trị')
  })
  it('đổi đơn vị tuổi thô ở lớp hiển thị', () => {
    expect(formatClinicalText('68.0 tuoi')).toBe('68,0 tuổi')
  })
})
