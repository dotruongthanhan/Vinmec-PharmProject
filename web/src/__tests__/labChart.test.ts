import { describe, expect, it } from 'vitest'
import type { ChiTietXetNghiemDong } from '../api/types.ts'
import { buildLabTrendCharts } from '../lib/labChart.ts'

describe('biểu đồ xu hướng xét nghiệm bằng SVG', () => {
  it('tạo thang đo hợp lệ với 2 điểm, đánh dấu điểm ngoài ngưỡng và mốc kê y lệnh', () => {
    const labs: ChiTietXetNghiemDong[] = [
      {
        thoi_diem_text: '10/11/2026 05:30',
        ten: 'Creatinin máu',
        gia_tri_text: '212,0 ▲',
        don_vi: 'umol/L',
        khoang_tham_chieu: '44,0 – 80,0',
        ngoai_nguong: true,
        huong: '▲',
      },
      {
        thoi_diem_text: '07/11/2026 05:30',
        ten: 'Creatinin máu',
        gia_tri_text: '150,0 ▲',
        don_vi: 'umol/L',
        khoang_tham_chieu: '44,0 – 80,0',
        ngoai_nguong: true,
        huong: '▲',
      },
      {
        thoi_diem_text: '10/11/2026 06:00',
        ten: 'CRP',
        gia_tri_text: '86,0 ▲',
        don_vi: 'mg/L',
        khoang_tham_chieu: '≤ 5,0',
        ngoai_nguong: true,
        huong: '▲',
      },
    ]

    const charts = buildLabTrendCharts(labs, '10/11/2026 05:50')
    expect(charts).toHaveLength(1)
    expect(charts[0].ten).toBe('Creatinin máu')
    expect(charts[0].donVi).toBe('µmol/L')
    expect(charts[0].points).toHaveLength(2)
    expect(charts[0].points[0].value).toBe(150)
    expect(charts[0].points[1].value).toBe(212)
    expect(charts[0].points.every((p) => p.ngoaiNguong)).toBe(true)
    expect(charts[0].referenceBand).not.toBeNull()
    expect(charts[0].orderMarker).not.toBeNull()
  })

  it('không chia cho 0 khi các giá trị bằng nhau và đánh dấu đúng điểm ngoài ngưỡng', () => {
    const equalLabs: ChiTietXetNghiemDong[] = [
      {
        thoi_diem_text: '08/11/2026 06:00',
        ten: 'Kali máu',
        gia_tri_text: '4,0',
        don_vi: 'mmol/L',
        khoang_tham_chieu: '',
        ngoai_nguong: false,
        huong: null,
      },
      {
        thoi_diem_text: '09/11/2026 06:00',
        ten: 'Kali máu',
        gia_tri_text: '4,0',
        don_vi: 'mmol/L',
        khoang_tham_chieu: '',
        ngoai_nguong: false,
        huong: null,
      },
    ]

    const charts = buildLabTrendCharts(equalLabs)
    expect(charts).toHaveLength(1)
    expect(charts[0].yMax).toBeGreaterThan(charts[0].yMin)
    for (const pt of charts[0].points) {
      expect(Number.isFinite(pt.x)).toBe(true)
      expect(Number.isFinite(pt.y)).toBe(true)
      expect(pt.ngoaiNguong).toBe(false)
    }
  })
})
