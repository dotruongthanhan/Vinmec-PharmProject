import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { MOCK_CASES } from '../api/mockData'
import type { DongHangDoi } from '../api/types'
import { OrdersTable } from '../features/orders/OrdersTable'

function renderRow(row: DongHangDoi): string {
  return renderToStaticMarkup(createElement(OrdersTable, {
    filterTitle: 'Tất cả y lệnh', orders: [row], totalCount: 1, loiNap: [], loading: false,
    error: null, searchQuery: '', sortField: 'ket_qua', sortDirection: 'desc',
    onToggleSort() {}, onOpenOrder() {}, onResetFilters() {}, onRetry() {},
  }))
}

describe('bảng danh sách theo hợp đồng v1.2', () => {
  it('giữ tám ô và để trống trường tuỳ chọn null hoặc vắng, không thay bằng mã ca', () => {
    const { ma_y_lenh: _code, thoi_diem_ke: _time, nguoi_benh_tom_tat: _patient, thuoc: _drugs, ...legacy } = MOCK_CASES.cases[0]
    for (const row of [legacy, { ...legacy, ma_y_lenh: null, thoi_diem_ke: null, nguoi_benh_tom_tat: null, thuoc: null }]) {
      const html = renderRow(row)
      const body = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(html)?.[1] ?? ''
      const cells = [...body.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) => m[1].replace(/<[^>]*>/g, ''))
      expect(cells).toHaveLength(8)
      expect([cells[1], cells[2], cells[3], cells[5]]).toEqual(['', '', '', ''])
    }
  })

  it('hiện mã y lệnh, thời điểm và thuốc đầu kèm số thuốc còn lại', () => {
    const html = renderRow({ ...MOCK_CASES.cases[0], thuoc: ['Thuốc giả lập A', 'Thuốc giả lập B', 'Thuốc giả lập C'] })
    expect(html).toContain('YL-DEMO-02')
    expect(html).toContain('05:50')
    expect(html).toContain('10/11')
    expect(html).toContain('Thuốc giả lập A')
    expect(html).toContain('+2')
    expect(html).toContain('title="Thuốc giả lập A, Thuốc giả lập B, Thuốc giả lập C"')
    expect(html).toContain(`title="${MOCK_CASES.cases[0].mo_ta}"`)
  })
})
