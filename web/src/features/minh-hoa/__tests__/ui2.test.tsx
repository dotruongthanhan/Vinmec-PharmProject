import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ClinicalMarkdown } from '@/components/ui/ClinicalMarkdown'
import { BangDuLieuGoc, KhungMinhHoa } from '../KhungMinhHoa'
import type { BoDuLieu } from '../nguPhap'
import fixture from '../mau/khoi-that-demo02-da-chinh.json'

const block = fixture[0]
const datasets = block.bo_du_lieu as BoDuLieu[]

describe('UI2', () => {
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
