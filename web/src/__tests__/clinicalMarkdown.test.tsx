import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { ClinicalMarkdown } from '../components/ui/ClinicalMarkdown.tsx'
import type { TrichDanTraLoi } from '../api/types.ts'

describe('ClinicalMarkdown component', () => {
  const sampleCitations: TrichDanTraLoi[] = [
    {
      so: 1,
      loai_ma: 'du_lieu',
      nhan: 'Xét nghiệm Creatinin',
      ban_ghi_id: 'XN-01',
    },
    {
      so: 2,
      loai_ma: 'tai_lieu',
      nhan: 'Hướng dẫn sử dụng Meropenem',
      ban_ghi_id: null,
    },
  ]

  it('render danh sách có thứ tự 1), 2) và tự động nhận diện chip mã ca, mã y lệnh, mã thuốc', () => {
    const text = `Dựa trên tổng quan hàng đợi y lệnh hiện có:
1) Ca DEMO-02, mã y lệnh YL-DEMO-02: kê T-MEROPENEM-1G với CrCl = 16,0 mL/min [1].
2) Ca DEMO-06, mã y lệnh YL-DEMO-06: kê T-AMOXICILLIN-500 [2].`

    const html = renderToStaticMarkup(
      createElement(ClinicalMarkdown, {
        text,
        citations: sampleCitations,
      }),
    )

    // Kiểm tra danh sách có thứ tự được render thành ol và li
    expect(html).toContain('<ol')
    expect(html).toContain('<li')

    // Kiểm tra các thực thể lâm sàng được bọc trong code chip
    expect(html).toContain('<code')
    expect(html).toContain('DEMO-02')
    expect(html).toContain('YL-DEMO-02')
    expect(html).toContain('T-MEROPENEM-1G')
    expect(html).toContain('DEMO-06')
    expect(html).toContain('YL-DEMO-06')
    expect(html).toContain('T-AMOXICILLIN-500')

    // Kiểm tra nút trích dẫn [1] và [2]
    expect(html).toContain('[1]')
    expect(html).toContain('[2]')
    expect(html).toContain('Mở trích dẫn [1]')
    expect(html).toContain('Mở trích dẫn [2]')
  })

  it('render danh sách gạch đầu dòng • và khối trích dẫn >', () => {
    const text = `Kiểm tra các mục:
• /api/health trả về 200
• /api/cases trả về danh sách y lệnh
> Ghi chú cảnh báo từ chuyên gia`

    const html = renderToStaticMarkup(
      createElement(ClinicalMarkdown, { text }),
    )

    expect(html).toContain('<ul')
    expect(html).toContain('/api/health')
    expect(html).toContain('/api/cases')
    expect(html).toContain('<blockquote')
    expect(html).toContain('Ghi chú cảnh báo từ chuyên gia')
  })

  it('render công thức toán học LaTeX inline và display an toàn', () => {
    const text = `Chỉ số tính toán: $CrCl \\le 25$ và display:
$$\\frac{A}{B}$$`

    const html = renderToStaticMarkup(
      createElement(ClinicalMarkdown, { text }),
    )

    // Ký hiệu \le được đổi thành ≤
    expect(html).toContain('CrCl ≤ 25')
    // Phân số có tử số và mẫu số
    expect(html).toContain('A')
    expect(html).toContain('B')
  })

  it('render in đậm **text** và inline code `uv run uvicorn`', () => {
    const text = `Khởi động lại bằng **chế độ nền**: \`uv run uvicorn app.api.main:app --port 8000\`.`

    const html = renderToStaticMarkup(
      createElement(ClinicalMarkdown, { text }),
    )

    expect(html).toContain('<strong')
    expect(html).toContain('chế độ nền')
    expect(html).toContain('uv run uvicorn app.api.main:app --port 8000')
  })
})
