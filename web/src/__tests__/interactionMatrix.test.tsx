import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
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
