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
        filterTitle: 'Tất cả người bệnh',
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

describe('bảng danh sách người bệnh chờ duyệt 10 cột', () => {
  it('giữ 10 ô dữ liệu và hiển thị dấu gạch/Chưa ghi nhận khi trường tuỳ chọn null hoặc vắng', () => {
    const {
      ma_y_lenh: _code,
      thoi_diem_ke: _time,
      thoi_diem_ke_xa_nhat: _oldest,
      thoi_diem_ke_gan_nhat: _latest,
      nguoi_benh_id: _pid,
      ho_ten: _name,
      chan_doan: _diags,
      chan_doan_chinh: _mainDiag,
      nguoi_benh_tom_tat: _patient,
      thuoc: _drugs,
      ...legacy
    } = MOCK_CASES.cases[0]

    for (const row of [
      legacy,
      {
        ...legacy,
        ma_y_lenh: null,
        thoi_diem_ke: null,
        thoi_diem_ke_xa_nhat: null,
        thoi_diem_ke_gan_nhat: null,
        nguoi_benh_id: null,
        ho_ten: null,
        chan_doan: null,
        chan_doan_chinh: null,
        nguoi_benh_tom_tat: null,
        thuoc: null,
      },
    ]) {
      const html = renderRow(row)
      const body = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(html)?.[1] ?? ''
      const cells = [...body.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) =>
        m[1].replace(/<[^>]*>/g, ''),
      )
      expect(cells).toHaveLength(10)
      expect([cells[1], cells[2], cells[3], cells[4], cells[6]]).toEqual([
        '—',
        '—',
        '—',
        'Chưa ghi nhận',
        'Chưa ghi nhận',
      ])
    }
  })

  it('hiện đủ 10 cột: ưu tiên, kê xa nhất, kê gần nhất, mã BN, họ tên, khoa, chẩn đoán (kèm ICD-10 ngay bên phải khoa), số đơn chờ, trạng thái NB và icon AI', () => {
    const html = renderRow(MOCK_CASES.cases[0])
    const headers = [...html.matchAll(/<th[^>]*>([\s\S]*?)<\/th>/g)].map((m) =>
      m[1].replace(/<[^>]*>/g, '').trim(),
    )
    expect(headers).toEqual([
      'Ưu tiên',
      'Kê xa nhất',
      'Kê gần nhất',
      'Mã BN',
      'Họ tên',
      'Khoa',
      'Chẩn đoán',
      'Đơn chờ',
      'Trạng thái NB',
      'AI',
    ])
    expect(html).toContain('Cao')
    expect(html).toContain('05:50')
    expect(html).toContain('06:15')
    expect(html).toContain('NB-DEMO-02')
    expect(html).toContain('NGUYỄN THỊ 62')
    expect(html).toContain('Hô hấp')
    expect(html).toContain('Viêm phổi (J18.9); Tổn thương thận cấp (N17.9)')
    expect(html).toContain('>2<')
    expect(html).toContain('Chưa duyệt')
    expect(html).not.toContain('Nữ, 75 tuổi')
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
