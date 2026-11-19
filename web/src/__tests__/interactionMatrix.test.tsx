import type { ReactElement, ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { InteractionSection } from '../features/order-detail/InteractionSection.tsx'
import { InteractionMatrix } from '../features/order-detail/InteractionMatrix.tsx'
import type { MaTranTuongTac } from '../api/types.ts'

describe('ma trận có cấu trúc', () => {
  it('hiện lý do tiếp cận bằng bàn phím, thức ăn và nguồn kể cả cặp không có nhận định', () => {
    const matrix: MaTranTuongTac = {
      nguon: 'DDInter 2.0 (sàng lọc, CC BY-NC-SA 4.0)', ghi_chu: 'Cần đối chiếu nhãn.',
      thuoc: ['P1', 'P2'].map((id) => ({
        chi_tiet_y_lenh_id: id, ten: 'Tên trùng', nhom: 'cho_duyet',
        phan_giai: 'khong_ap_dung', hoat_chat: [], ly_do: null,
      })),
      cap: [{ a: 'P1', b: 'P2', muc: 'khong_ap_dung', nhan_dinh_id: null, tom_tat: null, ly_do: 'Lý do dịch truyền' }],
      thuc_an: [{ chi_tiet_y_lenh_id: 'P1', hoat_chat: 'alpha', thuc_an: 'Fixture food', muc: 'chua_ro', mo_ta: 'Fixture source text', xu_tri: null }],
    }
    const html = renderToStaticMarkup(<InteractionMatrix
      choDuyet={{ cot: [], dong: [] }} dangDung={null}
      nhanDinh={{ can_chu_y: [], dat: [], yeu_to_chua_kiem: [] }}
      maTranTuongTac={matrix} onOpenFinding={() => {}}
    />)
    expect(html).toContain('Lý do dịch truyền')
    expect(html).toContain('tabindex="0"')
    expect(html).toContain('Fixture food')
    expect(html).toContain('Fixture source text')
    expect(html).toContain('CC BY-NC-SA 4.0')
    expect(html).toContain('Cần đối chiếu nhãn.')
    expect(html).toContain('Không có cặp áp dụng để sàng lọc tương tác')
    expect(html).not.toContain('Không ghi nhận tương tác ở mức cần lưu ý trở lên')
  })
})

describe('mục Yếu tố 4 thu gọn', () => {
  const matrix: MaTranTuongTac = {
    nguon: 'DDInter', ghi_chu: 'ghi chú',
    thuoc: ['P1', 'P2', 'P3'].map((id) => ({
      chi_tiet_y_lenh_id: id, ten: `Thuốc ${id}`, nhom: 'cho_duyet' as const,
      phan_giai: 'da_phan_giai' as const, hoat_chat: [], ly_do: null,
    })),
    cap: [
      { a: 'P1', b: 'P2', muc: 'nghiem_trong', nhan_dinh_id: null, tom_tat: 'Cặp nặng', ly_do: null },
      { a: 'P1', b: 'P3', muc: 'khong_phat_hien', nhan_dinh_id: null, tom_tat: null, ly_do: null },
    ],
    thuc_an: [],
  }
  const props = {
    choDuyet: { cot: [], dong: [] }, dangDung: null,
    nhanDinh: { can_chu_y: [], dat: [], yeu_to_chua_kiem: [] },
    maTranTuongTac: matrix, onOpenFinding: () => {},
  }

  it('thu gọn: tiêu đề, danh sách thuốc, chú giải, thẻ cặp vẫn hiện; chỉ lưới ẩn', () => {
    const html = renderToStaticMarkup(<InteractionSection {...props} open={false} onOpenChange={() => {}} />)
    expect(html).toContain('Yếu tố 4 · Tương tác thuốc')
    expect(html).toContain('Đối chiếu từng cặp thuốc')
    expect(html).toContain('THUỐC TRONG Y LỆNH')
    expect(html).toContain('Nghiêm trọng')
    expect(html).toContain('Thuốc P1 + Thuốc P2')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toMatch(/aria-controls="([^"]+)"/)
    expect(html).toContain('Ma trận tương tác')
    expect(html).toContain('3 thuốc · 1 cặp nghiêm trọng')
    expect(html.split('hidden=""').length - 1).toBe(1)
    const hidden = html.slice(html.indexOf('hidden=""'))
    const gridEnd = hidden.indexOf('</table>')
    expect(hidden.slice(0, gridEnd)).toContain('<table')
    // Chú giải và thẻ cặp nằm ngoài phần ẩn (thẻ cặp sau lưới).
    expect(html.indexOf('Nghiêm trọng')).toBeLessThan(html.indexOf('hidden=""'))
    expect(hidden.slice(gridEnd)).toContain('Thuốc P1 + Thuốc P2')
    expect(hidden.slice(0, gridEnd)).not.toContain('Thuốc P1 + Thuốc P2')
  })

  it('mở: aria-expanded=true, không còn phần hidden', () => {
    const html = renderToStaticMarkup(<InteractionSection {...props} open onOpenChange={() => {}} />)
    expect(html).toContain('aria-expanded="true"')
    expect(html).not.toContain('hidden=""')
    expect(html).toContain('<table')
  })

  it('bấm nút ma trận đảo trạng thái qua onOpenChange', () => {
    const onOpenChange = vi.fn()
    const section = InteractionSection({ ...props, open: false, onOpenChange }) as ReactElement<{ children: ReactNode[] }>
    const matrix = (section.props.children as ReactElement<{ matrixToggle: { onOpenChange: (v: boolean) => void } }>[])[1]
    matrix.props.matrixToggle.onOpenChange(true)
    expect(onOpenChange).toHaveBeenCalledWith(true)
  })

  it('không có matrixToggle (trang tra tay): ma trận luôn mở, không có nút', () => {
    const html = renderToStaticMarkup(<InteractionMatrix {...props} manual />)
    expect(html).not.toContain('aria-expanded')
    expect(html).not.toContain('hidden=""')
  })
})
