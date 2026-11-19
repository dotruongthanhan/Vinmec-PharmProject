import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { MaTranTuongTac } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'

function renderDetail(matrix: MaTranTuongTac | null): string {
  const detail = { ...MOCK_CASE_DETAILS['DEMO-02'], ma_tran_tuong_tac: matrix }
  return renderToStaticMarkup(
    <TooltipProvider><MemoryRouter initialEntries={['?tab=tham_dinh']}>
      <OrderDetailView detail={detail} aiTrangThai="tat" aiKetQua={null} aiThoiGianMs={null}
        aiCanhBao={[]} sessionFeedbackForCase={{}} onRerunAi={() => {}}
        isFeedbackSubmitting={() => false} getFeedbackError={() => null}
        onSubmitFeedback={async () => true} onClearFeedbackError={() => {}}
        onOpenEvidence={() => {}} onAskAboutFinding={() => {}} />
    </MemoryRouter></TooltipProvider>,
  )
}

describe('ma trận trong màn hình chi tiết', () => {
  it('truyền mức và nguồn có cấu trúc vào ma trận', () => {
    const html = renderDetail({
      nguon: 'DDInter nguồn kiểm thử', ghi_chu: 'Giới hạn sàng lọc kiểm thử',
      thuoc: ['P1', 'P2'].map((id) => ({
        chi_tiet_y_lenh_id: id, ten: `Thuốc giả lập ${id}`, nhom: 'cho_duyet',
        phan_giai: 'da_phan_giai', hoat_chat: [], ly_do: null,
      })),
      cap: [{ a: 'P1', b: 'P2', muc: 'nghiem_trong', nhan_dinh_id: null,
        tom_tat: 'Cặp nguồn kiểm thử Major', ly_do: null }],
      thuc_an: [],
    })
    expect(html).toContain('DDInter nguồn kiểm thử')
    expect(html).toContain('Giới hạn sàng lọc kiểm thử')
    expect(html).toContain('Cặp nguồn kiểm thử Major')
    expect(html).toContain('Thuốc giả lập P1')
    expect(html).toContain('Thuốc giả lập P2')
  })

  it('giữ cách hiển thị cũ khi ma trận null', () => {
    const html = renderDetail(null)
    expect(html).toContain('Meropenem 1 g')
    expect(html).not.toContain('DDInter nguồn kiểm thử')
    expect(html).toContain('Yếu tố 4 · Tương tác thuốc')
  })
})

describe('lưới ma trận thu gọn mặc định trong chi tiết ca', () => {
  it('mục luôn hiện, nút Ma trận tương tác aria-expanded=false, lưới ẩn', () => {
    const html = renderDetail({
      nguon: 'DDInter', ghi_chu: 'ghi chú',
      thuoc: ['P1', 'P2'].map((id) => ({
        chi_tiet_y_lenh_id: id, ten: `Thuốc giả lập ${id}`, nhom: 'cho_duyet' as const,
        phan_giai: 'da_phan_giai' as const, hoat_chat: [], ly_do: null,
      })),
      cap: [{ a: 'P1', b: 'P2', muc: 'nghiem_trong', nhan_dinh_id: null, tom_tat: 'Cặp nặng', ly_do: null }],
      thuc_an: [],
    })
    expect(html).toContain('Yếu tố 4 · Tương tác thuốc')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('Ma trận tương tác')
    expect(html).toContain('Cặp nặng')
    expect(html).toContain('hidden=""')
  })
})
