import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, expectTypeOf, it } from 'vitest'
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

describe('bảng Chi tiết y lệnh hợp nhất trong hồ sơ', () => {
  it('hiển thị toàn bộ dòng thuốc mọi y lệnh trong một bảng Chi tiết y lệnh và đếm đủ dòng', () => {
    const rendered = html()
    expect(rendered).toContain('Y lệnh (2)')
    expect(rendered).toContain('Chi tiết y lệnh')
    expect(rendered).toContain('Thuốc cũ giả lập')
    expect(rendered).toContain('Meropenem 1 g')
    expect(rendered).not.toContain('Chọn y lệnh')
    expect(rendered).not.toContain('Thông tin y lệnh')
    expect(selectMedicalOrder(detail.danh_sach_y_lenh!, null)?.y_lenh_id).toBe('YL-TT')
  })
  it('URL ?yl=YL-CU tự động mở rộng ngăn chi tiết của y lệnh cũ kèm khoa kê và lý do ngừng', () => {
    const rendered = html('?tab=y_lenh&yl=YL-CU')
    expect(rendered).toContain('Thuốc cũ giả lập')
    expect(rendered).toContain('Khoa cũ giả lập')
    expect(rendered).toContain('Đổi y lệnh giả lập')
    expect(rendered).toContain('aria-expanded="true"')
  })
  it('tham số chọn y lệnh giữ URL và mã không hợp lệ về trọng tâm', () => {
    const params = orderSelectionParams(new URLSearchParams('tab=dien_bien&khac=1'), 'YL CU/+')
    expect(params.get('tab')).toBe('y_lenh')
    expect(params.get('yl')).toBe('YL CU/+')
    expect(params.get('khac')).toBe('1')
    expect(selectMedicalOrder([old, focus], 'khong-co')).toBe(focus)
    expect(selectMedicalOrder([{ ...focus, y_lenh_id: 'YL-CA-KHAC' }], 'YL-CU')?.y_lenh_id).toBe('YL-CA-KHAC')
  })
  it('lựa chọn nhóm theo lần vào viện, có tên thuốc và mục được chọn', () => {
    const rendered = renderToStaticMarkup(<OrderChoices orders={[old, focus]} selectedId="YL-TT"
      detail={detail} onSelect={() => {}} />)
    expect(rendered).toContain('Lần vào viện 1')
    expect(rendered).toContain('Lần vào viện 2')
    expect(rendered).toContain('role="listbox"')
    expect(rendered).toContain('aria-label="Chọn y lệnh"')
    expect(rendered).toContain('Thuốc cũ giả lập')
    expect(rendered).toContain('aria-selected="true"')
    expect(rendered).not.toContain('aria-label="YL-CU')
  })
  it('y lệnh nền trong mock cũ không hiện nhận định của y lệnh trọng tâm', () => {
    const value = { ...old, cot: [...old.cot, 'Nhận định'],
      dong: old.dong.map((row) => ({ ...row, 'Nhận định': 'CẢNH BÁO TRỌNG TÂM' })) }
    const rendered = renderToStaticMarkup(<SelectedOrderDetails order={value} />)
    expect(rendered).not.toContain('CẢNH BÁO TRỌNG TÂM')
    expect(rendered).toContain('Chưa có thẩm định cho y lệnh này')
  })

  it('bỏ tab Phiếu điều trị khỏi thanh tab và giữ đếm gộp ở Diễn biến', () => {
    const rendered = html('?tab=y_lenh')
    expect(rendered).not.toContain('Phiếu điều trị (')
    expect(rendered).toContain('Diễn biến (')
    expect(rendered).toContain('<span>Thẩm định</span>')
  })
})

describe('phiếu điều trị gộp trong tab Diễn biến', () => {
  it('kiểu phiếu không cần metadata nạp tệp', () => {
    expectTypeOf<TreatmentSheet>().not.toHaveProperty('nguon_tep')
    expectTypeOf<TreatmentSheet>().not.toHaveProperty('nap_luc')
  })

  it('hiện chú thích thay cho liên kết đến mã y lệnh không tồn tại trong tab Diễn biến', () => {
    const rendered = html('?tab=dien_bien', { ...detail, phieu_dieu_tri: [
      { ...sheet, y_lenh_trong_ngay: ['YL-CU', 'YL-THIEU'] },
    ] })
    expect(rendered).toContain('tab=y_lenh&amp;yl=YL-CU')
    expect(rendered).toContain('Y lệnh YL-THIEU không có trong danh sách')
    expect(rendered).not.toContain('yl=YL-THIEU')
  })

  it('gộp Thông tin điều trị, Cập nhật diễn biến và Phiếu điều trị theo lần vào viện', () => {
    const rendered = html('?tab=dien_bien')
    expect(rendered).toContain('Thông tin điều trị')
    expect(rendered).toContain('Cập nhật diễn biến')
    expect(rendered).toContain('Phiếu điều trị')
    for (const text of ['Lần vào viện 1', 'Lần vào viện 2', 'Ngày điều trị 1', 'Bác sĩ trực',
      'Diễn biến giả lập', 'Đánh giá giả lập', 'Xử trí giả lập', 'Theo dõi giả lập', 'Dặn dò giả lập']) {
      expect(rendered).toContain(text)
    }
    expect(rendered).toContain('tab=y_lenh&amp;yl=YL-CU')
  })
  it('URL ?tab=phieu_dieu_tri cũ tự chuyển về nội dung tab Diễn biến và mảng rỗng hiện trạng thái rỗng ở Diễn biến', () => {
    const bare = { ...detail, phieu_dieu_tri: [], chi_tiet: { ...detail.chi_tiet, dien_bien: [] } }
    const rendered = html('?tab=phieu_dieu_tri', bare)
    expect(rendered).toContain('Diễn biến (0)')
    expect(rendered).toContain('Cập nhật diễn biến')
    expect(rendered).toContain('Chưa có ghi nhận diễn biến')
    const empty = renderToStaticMarkup(<MemoryRouter><TreatmentSheets detail={bare} /></MemoryRouter>)
    expect(empty).toContain('Chưa có phiếu điều trị')
  })
  it('đổi đơn vị tuổi thô ở lớp hiển thị', () => {
    expect(formatClinicalText('68.0 tuoi')).toBe('68,0 tuổi')
  })
})
