import { Children, createElement, isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_CASES } from '../api/mockData'
import type { DongHangDoi } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { OrdersTable } from '../features/orders/OrdersTable'
import type { OrdersTableProps } from '../features/orders/OrdersTable'
import type { OrderColumnFilters } from '../lib/orders'

function renderRow(row: DongHangDoi, overrides: Partial<OrdersTableProps> = {}, table = OrdersTable): string {
  return renderToStaticMarkup(
    createElement(
      TooltipProvider,
      null,
      createElement(table, {
        filterTitle: 'Tất cả y lệnh',
        orders: [row],
        totalCount: 1,
        loiNap: [],
        loading: false,
        error: null,
        searchQuery: '',
        sortField: 'ket_qua',
        sortDirection: 'desc',
        columnFilters: {},
        onColumnFiltersChange() {},
        onToggleSort() {},
        onOpenOrder() {},
        onResetFilters() {},
        onRetry() {},
        onRefresh() {},
        ...overrides,
      }),
    ),
  )
}

type TreeProps = { children?: ReactNode; onClick?: () => void }
function elements(node: ReactNode): ReactElement<TreeProps>[] {
  return Children.toArray(node).flatMap((item) => isValidElement<TreeProps>(item)
    ? [item, ...elements(item.props.children)] : [])
}

describe('bảng danh sách y lệnh 8 cột (không có cột Thuốc, cảnh báo AI dạng icon)', () => {
  it('giữ 8 ô dữ liệu và để trống trường tuỳ chọn null hoặc vắng, không thay bằng mã ca', () => {
    const {
      ma_y_lenh: _code,
      thoi_diem_ke: _time,
      nguoi_benh_tom_tat: _patient,
      thuoc: _drugs,
      ...legacy
    } = MOCK_CASES.cases[0]

    for (const row of [
      legacy,
      { ...legacy, ma_y_lenh: null, thoi_diem_ke: null, nguoi_benh_tom_tat: null, thuoc: null },
    ]) {
      const html = renderRow(row)
      const body = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(html)?.[1] ?? ''
      const cells = [...body.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) =>
        m[1].replace(/<[^>]*>/g, ''),
      )
      expect(cells).toHaveLength(8)
      // Cột 2 (Thời điểm kê), 3 (Mã y lệnh), 4 (Mã BN), 5 (Người bệnh) để trống khi vắng dữ liệu
      expect([cells[1], cells[2], cells[3], cells[4]]).toEqual(['', '', '', ''])
    }
  })

  it('hiện ưu tiên, thời điểm kê, mã y lệnh, mã BN, người bệnh, khoa, trạng thái và icon cảnh báo AI kèm chú giải', () => {
    const html = renderRow(MOCK_CASES.cases[0])
    expect(html).toContain('Cao')
    expect(html).toContain('YL-DEMO-02')
    expect(html).toContain('NB-DEMO-02')
    expect(html).toContain('Nữ, 75 tuổi')
    expect(html).toContain('Hô hấp')
    expect(html).toContain('Chưa duyệt')
    expect(html).toContain('05:50')
    expect(html).toContain('10/11')
    expect(html).not.toContain('Meropenem 1 g')
    expect(html).toContain(`1 nghiêm trọng — ${MOCK_CASES.cases[0].mo_ta}`)
  })

  it('hiện số lựa chọn trên đầu cột và xóa cả bộ lọc cột lẫn tìm kiếm', () => {
    let tree: ReactNode
    const probe = (props: OrdersTableProps) => {
      tree = OrdersTable(props)
      return tree
    }
    let columnFilters: OrderColumnFilters = { priority: ['cao', 'trung_binh'], khoa: ['Hô hấp', 'Tim mạch'] }
    const onResetFilters = vi.fn()
    const row = MOCK_CASES.cases[0]
    const html = renderRow(row, {
      columnFilters, searchQuery: 'giả lập', onResetFilters,
      onColumnFiltersChange: (next) => {
        columnFilters = typeof next === 'function' ? next(columnFilters) : next
      },
    }, probe)
    expect(html).toContain('2<span class="sr-only"> lựa chọn đang lọc')
    expect(html).toContain('Ưu tiên: Cao, Trung bình')
    elements(tree).find((node) => node.props.children === 'Xóa tất cả bộ lọc')?.props.onClick?.()
    expect(columnFilters).toEqual({})
    expect(onResetFilters).toHaveBeenCalledOnce()
    expect(renderRow(row, { columnFilters })).not.toContain('Xóa tất cả bộ lọc')
  })

  it('hiện giờ +07 ở chân danh sách và bấm được để làm mới', () => {
    let tree: ReactNode
    const onRefresh = vi.fn()
    const html = renderRow(MOCK_CASES.cases[0], {
      onRefresh, updatedAt: new Date('2026-11-17T17:08:09Z'),
    }, (props) => {
      tree = OrdersTable(props)
      return tree
    })
    expect(html).toContain('Cập nhật lúc <time dateTime="2026-11-17T17:08:09.000Z">00:08:09</time>')
    elements(tree).find((node) => node.props.onClick === onRefresh)?.props.onClick?.()
    expect(onRefresh).toHaveBeenCalledOnce()
  })
})
