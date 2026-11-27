import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ClinicalMarkdown } from '@/components/ui/ClinicalMarkdown'
import { BangDuLieuGoc, KhungMinhHoa } from '../KhungMinhHoa'
import type { BoDuLieu } from '../nguPhap'
import fixture from '../mau/khoi-that-demo02-da-chinh.json'
import doanCases from './fixtures/doan.json'

const block = fixture[0]
const datasets = block.bo_du_lieu as BoDuLieu[]

describe('UI2', () => {
  it('dựng đoạn đang dùng trên trục thời gian và bảng giữ dữ liệu gốc', () => {
    const example = doanCases[0]
    const data = [example.bo_du_lieu as unknown as BoDuLieu]
    const html = renderToStaticMarkup(
      <TooltipProvider><KhungMinhHoa dacTa={example.dac_ta} boDuLieu={data} /></TooltipProvider>,
    )
    expect(html).toContain('aria-label="Xem dạng bảng"')
    expect(html).toContain('đang dùng')
    expect(html).toContain('<svg')
    const table = renderToStaticMarkup(<BangDuLieuGoc boDuLieu={data} />)
    expect(table).toContain('01/11/2026 08:00')
    expect(data[0].dong[0].bat_dau).toBe('2026-11-01T08:00:00+07:00')
    expect(table).toContain('bat_dau')
    expect(table).toContain('ket_thuc')
  })
  it('hiển thị nhãn cột và nhãn logic riêng', () => {
    const data: BoDuLieu[] = [{ ma: 'ds-1', cot: [
      { ten: 'ngoai', kieu: 'logic', don_vi: null, nhan: 'Ngoài ngưỡng' },
      { ten: 'can_chinh', kieu: 'logic', don_vi: null, nhan_dung: 'Cần chỉnh liều', nhan_sai: 'Không cần chỉnh' },
    ], dong: [{ ngoai: true, can_chinh: false }, { ngoai: false, can_chinh: true }] }]
    const html = renderToStaticMarkup(<BangDuLieuGoc boDuLieu={data} />)
    for (const text of ['Ngoài ngưỡng', 'Có', 'Không', 'Cần chỉnh liều', 'Không cần chỉnh']) expect(html).toContain(text)
  })
  it('shared expand button', () => {
    const table = renderToStaticMarkup(<TooltipProvider><ClinicalMarkdown text={'| A |\n| --- |\n| x |'} /></TooltipProvider>)
    const figure = renderToStaticMarkup(<TooltipProvider><KhungMinhHoa dacTa={block.dac_ta} boDuLieu={datasets} /></TooltipProvider>)
    expect(table).toContain('aria-label="Mở rộng bảng"')
    expect(figure).toContain('aria-label="Mở rộng hình"')
    expect(table).toContain('data-expand-button=""')
    expect(figure).toContain('data-expand-button=""')
    expect(figure).not.toContain('Toàn màn')
    expect(figure).toContain('aria-label="Xem dạng bảng"')
    expect(figure).toContain('aria-pressed="false"')
  })

  it('dataset labels', () => {
    const html = renderToStaticMarkup(<BangDuLieuGoc boDuLieu={datasets} />)
    const labels = [...html.matchAll(/<button[^>]*role="tab"[^>]*>(.*?)<\/button>/g)].map((match) => match[1])
    expect(labels).toHaveLength(3)
    expect(labels[0]).toContain('Giá trị của ca')
    expect(labels[1]).toContain('Mức liều')
    expect(labels[2]).toContain('Lưới CrCl theo creatinin')
    expect(labels.join('')).not.toContain('ds-')
  })
})
