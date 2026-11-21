import { Children, createElement, isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_CASES } from '../api/mockData'
import type { DongHangDoi } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { OrdersTable } from '../features/orders/OrdersTable'
import { TablePagination } from '../features/orders/TablePagination'
import type { OrdersTableProps } from '../features/orders/OrdersTable'
import type { OrderColumnFilters } from '../lib/orders'

function renderOrders(
  orders: readonly DongHangDoi[],
  overrides: Partial<OrdersTableProps> = {},
  table = OrdersTable,
): string {
  return renderToStaticMarkup(
    createElement(
      TooltipProvider,
      null,
      createElement(table, {
        filterTitle: 'Hồ sơ cần duyệt',
        orders,
        totalCount: orders.length,
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

function renderRow(row: DongHangDoi, overrides: Partial<OrdersTableProps> = {}, table = OrdersTable): string {
  return renderOrders([row], overrides, table)
}

function makeSampleCases(count: number): DongHangDoi[] {
  return Array.from({ length: count }, (_, idx) => {
    const seq = String(idx + 1).padStart(2, '0')
    return {
      ...MOCK_CASES.cases[0],
      ca_id: `CA-${seq}`,
      ma_y_lenh: `YL-${seq}`,
      thoi_diem_ke: `2026-11-10T${String(idx % 24).padStart(2, '0')}:15:00+07:00`,
      ho_ten: `Người bệnh ${seq}`,
      nguoi_benh_tom_tat: `Nam, ${30 + (idx % 50)} tuổi`,
      ngay_sinh: `19${50 + (idx % 40)}-05-10`,
      chan_doan_chinh: `Chẩn đoán mẫu ${seq}`,
      khoa: idx % 2 === 0 ? 'Hô hấp' : 'Tim mạch',
      uu_tien: (idx % 5) as 0 | 1 | 2 | 3 | 4,
    }
  })
}

type TreeProps = {
  children?: ReactNode
  onClick?: () => void
  'aria-label'?: string
}

function elements(node: ReactNode): ReactElement<TreeProps>[] {
  return Children.toArray(node).flatMap((item) => isValidElement<TreeProps>(item)
    ? [item, ...elements(item.props.children)] : [])
}

describe('bảng hồ sơ cần duyệt 9 cột (nhãn mới, cột mới, bỏ Mã y lệnh, phân trang 30 dòng)', () => {
  it('hiện đúng 9 cột theo thứ tự mới, bỏ Mã y lệnh / Vào viện / Y lệnh và ghi "Chưa ghi nhận" khi thiếu', () => {
    const {
      ma_y_lenh: _code,
      thoi_diem_ke: _time,
      nguoi_benh_tom_tat: _patient,
      thuoc: _drugs,
      ho_ten: _name,
      ngay_sinh: _dob,
      chan_doan_chinh: _diag,
      ...legacy
    } = MOCK_CASES.cases[0]

    for (const row of [
      legacy,
      {
        ...legacy,
        ma_y_lenh: null,
        thoi_diem_ke: null,
        nguoi_benh_tom_tat: null,
        thuoc: null,
        ho_ten: null,
        ngay_sinh: null,
        chan_doan_chinh: null,
        khoa: '',
      },
    ]) {
      const html = renderRow(row)
      const head = /<thead[^>]*>([\s\S]*?)<\/thead>/.exec(html)?.[1] ?? ''
      const headers = [...head.matchAll(/<th[^>]*>([\s\S]*?)<\/th>/g)].map((m) =>
        m[1].replace(/<[^>]*>/g, '').trim(),
      )
      expect(headers).toEqual([
        'Ưu tiên',
        'Thời điểm kê',
        'Mã BN',
        'Người bệnh',
        'Ngày sinh',
        'Khoa',
        'Chẩn đoán chính',
        'Trạng thái',
        'Cảnh báo AI',
      ])
      expect(html).not.toContain('Mã y lệnh')
      expect(html).not.toContain('Thời điểm vào viện')
      expect(html).not.toContain('Y lệnh (lần cuối)')

      const body = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(html)?.[1] ?? ''
      const cells = [...body.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) =>
        m[1].replace(/<[^>]*>/g, '').trim(),
      )
      expect(cells).toHaveLength(9)
      expect(cells[1]).toBe('Chưa ghi nhận')
      expect(cells[2]).toBe('—')
      expect(cells[3]).toBe('Chưa ghi nhận')
      expect(cells[4]).toBe('Chưa ghi nhận')
      expect(cells[6]).toBe('Chưa ghi nhận')
    }
  })

  it('hiện tiêu đề "Hồ sơ cần duyệt", bộ đếm "N hồ sơ", đủ dữ liệu 9 cột và không hiện Mã y lệnh', () => {
    const row: DongHangDoi = {
      ...MOCK_CASES.cases[0],
      ho_ten: 'Nguyễn Thị 62',
      ngay_sinh: '1951-11-10',
      chan_doan_chinh: 'Viêm phổi',
    }
    const html = renderRow(row)
    expect(html).toContain('Hồ sơ cần duyệt')
    expect(html).toContain('1 hồ sơ')
    expect(html).toContain('Cao')
    expect(html).toContain('05:50')
    expect(html).toContain('10/11')
    expect(html).toContain('NB-DEMO-02')
    expect(html).toContain('NGUYỄN THỊ 62')
    expect(html).toContain('Nữ, 75 tuổi')
    expect(html).toContain('10/11/1951')
    expect(html).toContain('Hô hấp')
    expect(html).toContain('Viêm phổi')
    expect(html).toContain('Chưa duyệt')
    expect(html).not.toContain('YL-DEMO-02')
    expect(html).not.toContain('Meropenem 1 g')
    expect(html).toContain(`1 nghiêm trọng — ${MOCK_CASES.cases[0].mo_ta}`)
  })

  it('phân trang 67 dòng: trang 1 có 30 dòng, trang 3 có 7 dòng và điều khiển Trước/Sau', () => {
    const rows = makeSampleCases(67)
    const htmlPage1 = renderOrders(rows, { sortField: 'ca_id', sortDirection: 'asc', page: 1 })
    const bodyPage1 = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(htmlPage1)?.[1] ?? ''
    expect(htmlPage1).toContain('67 hồ sơ')
    expect(htmlPage1).toContain('1–30 / 67')
    expect(bodyPage1.match(/<tr\b/g)).toHaveLength(30)
    expect(bodyPage1).toContain('NB-CA-01')
    expect(bodyPage1).toContain('NB-CA-30')
    expect(bodyPage1).not.toContain('NB-CA-31')

    const htmlPage3 = renderOrders(rows, { sortField: 'ca_id', sortDirection: 'asc', page: 3 })
    const bodyPage3 = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(htmlPage3)?.[1] ?? ''
    expect(htmlPage3).toContain('61–67 / 67')
    expect(bodyPage3.match(/<tr\b/g)).toHaveLength(7)
    expect(bodyPage3).toContain('NB-CA-61')
    expect(bodyPage3).toContain('NB-CA-67')
    expect(bodyPage3).not.toContain('NB-CA-60')

    let tree: ReactNode
    const onPageChange = vi.fn()
    renderOrders(
      rows,
      { sortField: 'ca_id', sortDirection: 'asc', page: 1, onPageChange },
      (props) => {
        tree = OrdersTable(props)
        return tree
      },
    )
    const pager = elements(tree).find((node) => node.type === TablePagination)
    expect(pager).toBeDefined()
    ;(pager!.props as unknown as { onPageChange: (page: number) => void }).onPageChange(2)
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('áp dụng sắp xếp trên toàn bộ danh sách trước khi cắt trang 30 dòng', () => {
    const rows: DongHangDoi[] = makeSampleCases(67).map((item) => ({
      ...item,
      uu_tien: 4 as const,
      ho_ten: `Zed ${item.ca_id}`,
      ngay_sinh: '1990-01-01',
    }))
    // Đặt hồ sơ ưu tiên cao / tên đầu bảng / sinh sớm nhất ở cuối mảng nguồn (vị trí 67).
    rows[66] = {
      ...rows[66],
      ca_id: 'CA-TOP',
      uu_tien: 0,
      ho_ten: 'An Văn Đầu',
      ngay_sinh: '1940-01-01',
    }

    const byPriority = renderOrders(rows, {
      sortField: 'ket_qua',
      sortDirection: 'desc',
      page: 1,
    })
    expect(byPriority).toContain('NB-CA-TOP')

    const byName = renderOrders(rows, {
      sortField: 'nguoi_benh',
      sortDirection: 'asc',
      page: 1,
    })
    expect(byName).toContain('NB-CA-TOP')

    const byDob = renderOrders(rows, {
      sortField: 'ngay_sinh',
      sortDirection: 'asc',
      page: 1,
    })
    expect(byDob).toContain('NB-CA-TOP')
  })

  it('hiện số lựa chọn trên đầu cột, xóa bộ lọc lẫn tìm kiếm và đưa về trang 1 khi đổi bộ lọc', () => {
    let tree: ReactNode
    const probe = (props: OrdersTableProps) => {
      tree = OrdersTable(props)
      return tree
    }
    let columnFilters: OrderColumnFilters = { priority: ['cao', 'trung_binh'], khoa: ['Hô hấp', 'Tim mạch'] }
    const onResetFilters = vi.fn()
    const onPageChange = vi.fn()
    const rows = makeSampleCases(67)
    const html = renderOrders(rows, {
      page: 2,
      onPageChange,
      columnFilters,
      searchQuery: 'giả lập',
      onResetFilters,
      onColumnFiltersChange: (next) => {
        columnFilters = typeof next === 'function' ? next(columnFilters) : next
      },
    }, probe)
    expect(html).toContain('2<span class="sr-only"> lựa chọn đang lọc')
    expect(html).toContain('Ưu tiên: Cao, Trung bình')

    elements(tree).find((node) => node.props['aria-label'] === 'Bỏ lọc ưu tiên')?.props.onClick?.()
    expect(onPageChange).toHaveBeenCalledWith(1)
    expect(columnFilters.priority).toEqual([])

    onPageChange.mockClear()
    elements(tree).find((node) => node.props.children === 'Xóa tất cả bộ lọc')?.props.onClick?.()
    expect(columnFilters).toEqual({})
    expect(onResetFilters).toHaveBeenCalledOnce()
    expect(onPageChange).toHaveBeenCalledWith(1)
    expect(renderRow(rows[0], { columnFilters })).not.toContain('Xóa tất cả bộ lọc')
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
