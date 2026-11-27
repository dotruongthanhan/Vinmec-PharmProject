import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { ChiTietCa, TreatmentSheet } from '../api/types'
import { ProgressTabContent } from '../features/order-detail/ProgressTabContent'

describe('ProgressTabContent (Tab Diễn biến hợp nhất)', () => {
  it('hiển thị "Không nằm viện" cho bệnh nhân ngoại trú và tiêu đề bảng "Cập nhật diễn biến"', () => {
    const demo03 = MOCK_CASE_DETAILS['DEMO-03']
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <ProgressTabContent detail={demo03} />
      </MemoryRouter>,
    )

    expect(html).toContain('Thông tin điều trị')
    expect(html).toContain('Thời gian nằm viện')
    expect(html).toContain('Không nằm viện')
    expect(html).toContain('Cập nhật diễn biến')
  })

  it('gộp cả Phiếu điều trị vào trong tab Diễn biến và giữ số ngày nằm viện cho nội trú', () => {
    const demo02 = MOCK_CASE_DETAILS['DEMO-02']
    const sheet: TreatmentSheet = {
      phieu_dieu_tri_id: 'PDT-TEST-1',
      dot_dieu_tri_id: 'DT-TEST-1',
      thu_tu_dot: 1,
      ngay_dieu_tri: 1,
      thoi_diem_lap: '2026-11-10T08:30:00+07:00',
      vai_tro_nguoi_lap: 'bac_si_dieu_tri',
      dien_bien: 'Diễn biến trong phiếu điều trị',
      danh_gia: 'Đánh giá lâm sàng',
      huong_xu_tri: 'Xử trí kháng sinh',
      che_do_cham_soc: 'cấp 2',
      che_do_an: 'Ăn nhạt',
      theo_doi: ['Theo dõi chức năng thận'],
      dan_do: null,
      y_lenh_trong_ngay: ['YL-DEMO-02'],
    }
    const detailWithSheet: ChiTietCa = { ...demo02, phieu_dieu_tri: [sheet] }

    const html = renderToStaticMarkup(
      <MemoryRouter>
        <ProgressTabContent detail={detailWithSheet} />
      </MemoryRouter>,
    )

    expect(html).toContain('Thông tin điều trị')
    expect(html).not.toContain('Không nằm viện')
    expect(html).toContain('Cập nhật diễn biến')
    expect(html).toContain('Phiếu điều trị')
    expect(html).toContain('Diễn biến trong phiếu điều trị')
  })
})
