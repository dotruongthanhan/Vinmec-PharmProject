import { describe, expect, it } from 'vitest'
import { MOCK_CASES } from '../api/mockData.ts'
import type { DongHangDoi } from '../api/types.ts'
import {
  ORDER_FILTER_LABELS,
  applyOrderColumnFilters,
  countOrderGroups,
  extractOrderDateYmd,
  filterOrders,
  getOrderPriorityLevel,
  getOrderWorkflowStatus,
  sortOrders,
} from '../lib/orders.ts'
import type { OrderRowInput } from '../lib/orders.ts'
import {
  DEFAULT_PAGE_SIZE,
  getVisiblePageNumbers,
  paginateItems,
  parsePageParam,
  updatePageInSearchParams,
} from '../lib/pagination.ts'

describe('bộ lọc và đếm nhóm thanh bên trên dữ liệu giả 6 ca', () => {
  it('tính đúng tổng từng nhóm và từng khoa trên 6 ca giả lập', () => {
    const counts = countOrderGroups(MOCK_CASES.cases)
    expect(counts.tat_ca).toBe(6)
    expect(counts.can_xem).toBe(3)
    expect(counts.thieu_du_lieu).toBe(1)
    expect(counts.dat).toBe(2)
    expect(counts.da_phan_hoi).toBe(0)

    const deptTotal = counts.departments.reduce((sum, item) => sum + item.count, 0)
    expect(deptTotal).toBe(6)
  })

  it('ca có cả nghiêm trọng và thiếu dữ liệu được đếm đúng ở cả hai nhóm', () => {
    const mixedCase: DongHangDoi = {
      ca_id: 'CA-MIXED',
      khoa: 'Hồi sức',
      mo_ta: 'Ca vừa nghiêm trọng vừa thiếu dữ liệu',
      uu_tien: 0,
      huy_hieu: '1 nghiêm trọng, 1 thiếu dữ liệu',
      so_nghiem_trong: 1,
      so_can_luu_y: 0,
      so_thieu_du_lieu: 1,
      da_phan_hoi_het: false,
    }
    const cases = [...MOCK_CASES.cases, mixedCase]
    const counts = countOrderGroups(cases)

    expect(counts.tat_ca).toBe(7)
    expect(counts.can_xem).toBe(4)
    expect(counts.thieu_du_lieu).toBe(2)

    const reviewList = filterOrders(cases, { type: 'group', group: 'can_xem' })
    const missingList = filterOrders(cases, { type: 'group', group: 'thieu_du_lieu' })
    expect(reviewList.some((c) => c.ca_id === 'CA-MIXED')).toBe(true)
    expect(missingList.some((c) => c.ca_id === 'CA-MIXED')).toBe(true)
  })
})

describe('sắp xếp danh sách y lệnh', () => {
  const sampleRows: OrderRowInput[] = [
    {
      ca_id: 'CA-1',
      khoa: 'Tim mạch',
      mo_ta: 'Ca đạt',
      uu_tien: 4,
      huy_hieu: 'Đạt',
      so_nghiem_trong: 0,
      so_can_luu_y: 0,
      so_thieu_du_lieu: 0,
      da_phan_hoi_het: false,
      thoi_diem_ke: '10/11/2026 07:00',
    },
    {
      ca_id: 'CA-2',
      khoa: 'Hô hấp',
      mo_ta: 'Ca nghiêm trọng sau',
      uu_tien: 0,
      huy_hieu: '1 nghiêm trọng',
      so_nghiem_trong: 1,
      so_can_luu_y: 0,
      so_thieu_du_lieu: 0,
      da_phan_hoi_het: false,
      thoi_diem_ke: '10/11/2026 09:00',
    },
    {
      ca_id: 'CA-3',
      khoa: 'Hô hấp',
      mo_ta: 'Ca nghiêm trọng trước A',
      uu_tien: 0,
      huy_hieu: '1 nghiêm trọng',
      so_nghiem_trong: 1,
      so_can_luu_y: 0,
      so_thieu_du_lieu: 0,
      da_phan_hoi_het: false,
      thoi_diem_ke: '10/11/2026 06:00',
    },
    {
      ca_id: 'CA-4',
      khoa: 'Hô hấp',
      mo_ta: 'Ca nghiêm trọng bằng giờ B',
      uu_tien: 0,
      huy_hieu: '1 nghiêm trọng',
      so_nghiem_trong: 1,
      so_can_luu_y: 0,
      so_thieu_du_lieu: 0,
      da_phan_hoi_het: false,
      thoi_diem_ke: '10/11/2026 06:00',
    },
  ]

  it('sắp xếp mặc định mức nghiêm trọng giảm dần rồi thời điểm kê và ổn định khi bằng nhau', () => {
    const sorted = sortOrders(sampleRows, 'ket_qua', 'desc')
    expect(sorted.map((r) => r.ca_id)).toEqual(['CA-3', 'CA-4', 'CA-2', 'CA-1'])
  })

  it('đảo chiều sắp xếp theo Kết quả khi chọn asc', () => {
    const sorted = sortOrders(sampleRows, 'ket_qua', 'asc')
    expect(sorted[0].ca_id).toBe('CA-1')
  })
})

describe('tìm kiếm y lệnh phía trình duyệt', () => {
  const rows: OrderRowInput[] = [
    { ...MOCK_CASES.cases[0], ca_id: 'CA-A', khoa: 'Khoa A', uu_tien: 0, trang_thai_y_lenh: 'chua_duyet' },
    { ...MOCK_CASES.cases[0], ca_id: 'CA-B', khoa: 'Khoa B', uu_tien: 1, trang_thai_y_lenh: 'dang_cho' },
    { ...MOCK_CASES.cases[0], ca_id: 'CA-C', khoa: 'Khoa C', uu_tien: 1, trang_thai_y_lenh: 'da_huy' },
    { ...MOCK_CASES.cases[4], ca_id: 'CA-D', khoa: 'Khoa B', uu_tien: 4, trang_thai_y_lenh: 'da_duyet' },
  ]
  const all = { type: 'group', group: 'tat_ca' } as const

  it('lấy hợp của hai mức ưu tiên hoặc hai khoa', () => {
    expect(filterOrders(rows, all, '', { priority: ['cao', 'trung_binh'] })).toEqual(rows.slice(0, 3))
    expect(filterOrders(rows, all, '', { khoa: ['Khoa A', 'Khoa B'] })).toEqual([rows[0], rows[1], rows[3]])
  })

  it('lấy giao giữa các cột, kể cả trạng thái và cảnh báo', () => {
    expect(filterOrders(rows, all, '', {
      priority: ['trung_binh', 'thap'], khoa: ['Khoa A', 'Khoa B'],
      status: ['dang_cho', 'da_duyet'], aiWarning: ['nghiem_trong', 'can_luu_y'],
    })).toEqual([rows[1]])
    expect(countOrderGroups(rows, { khoa: ['Khoa A', 'Khoa C'] })).toMatchObject({
      tat_ca: 2,
      departments: [{ khoa: 'Khoa A', count: 1 }, { khoa: 'Khoa C', count: 1 }],
    })
  })

  it('mảng rỗng và all không lọc, giá trị đơn vẫn lọc', () => {
    expect(filterOrders(rows, all, '', { priority: [], khoa: [], status: [], aiWarning: [] })).toEqual(rows)
    expect(filterOrders(rows, all, '', { priority: 'all', khoa: 'Khoa B' })).toEqual([rows[1], rows[3]])
  })

  it('tìm thuốc trong danh sách v1.2 và chấp nhận trường tuỳ chọn null hoặc vắng', () => {
    const row = { ...MOCK_CASES.cases[0], thuoc: ['Thuốc thử A', 'Thuốc thử B'] }
    expect(filterOrders([row], { type: 'group', group: 'tat_ca' }, 'thuoc thu b')).toEqual([row])
    expect(filterOrders([{ ...row, thuoc: null }], { type: 'group', group: 'tat_ca' }, 'khong co')).toEqual([])
  })
  it('không phân biệt hoa thường và dấu tiếng Việt', () => {
    const byDept = filterOrders(
      MOCK_CASES.cases,
      { type: 'group', group: 'tat_ca' },
      'HO HAP',
    )
    expect(byDept.map((c) => c.ca_id)).toEqual(['DEMO-02', 'DEMO-06'])

    const byMissingD = filterOrders(
      MOCK_CASES.cases,
      { type: 'group', group: 'tat_ca' },
      'chan thuong',
    )
    expect(byMissingD.map((c) => c.ca_id)).toEqual(['DEMO-04'])

    const byDrug = filterOrders(
      MOCK_CASES.cases,
      { type: 'group', group: 'tat_ca' },
      'MEROPENEM',
    )
    expect(byDrug.map((c) => c.ca_id)).toEqual(['DEMO-02'])
  })

  it('lọc và sắp xếp theo từng cột (ưu tiên, khoa, trạng thái, ngày lịch và giờ nhập tay)', () => {
    expect(extractOrderDateYmd('2026-11-10T05:50:00+07:00')).toBe('2026-11-10')
    expect(getOrderPriorityLevel(MOCK_CASES.cases[0])).toBe('cao')
    expect(getOrderWorkflowStatus(MOCK_CASES.cases[0])).toBe('chua_duyet')
    expect(getOrderWorkflowStatus(MOCK_CASES.cases[3])).toBe('dang_cho')

    const byDateAndTime = applyOrderColumnFilters(MOCK_CASES.cases, {
      dateExact: '2026-11-10',
      timeText: '05:50',
    })
    expect(byDateAndTime.map((c) => c.ca_id)).toEqual(['DEMO-02'])

    const byStatusOnHold = applyOrderColumnFilters(MOCK_CASES.cases, {
      status: 'dang_cho',
    })
    expect(byStatusOnHold.map((c) => c.ca_id)).toEqual(['DEMO-03'])

    const sortedByDeptAsc = sortOrders(MOCK_CASES.cases, 'khoa', 'asc')
    expect(sortedByDeptAsc[0].khoa).toBe('Chấn thương chỉnh hình')
  })

  it('nhãn gốc là Hồ sơ cần duyệt và hỗ trợ sắp xếp ngày sinh, chẩn đoán, họ tên, tìm theo ngày sinh', () => {
    expect(ORDER_FILTER_LABELS.tat_ca).toBe('Hồ sơ cần duyệt')
    const rowsWithDemographics: OrderRowInput[] = [
      {
        ...MOCK_CASES.cases[0],
        ca_id: 'CA-A',
        ho_ten: 'Lê Thị B',
        ngay_sinh: '1980-05-12',
        chan_doan_chinh: 'Viêm phổi',
      },
      {
        ...MOCK_CASES.cases[0],
        ca_id: 'CA-B',
        ho_ten: 'Nguyễn Văn A',
        ngay_sinh: null,
        chan_doan_chinh: null,
      },
      {
        ...MOCK_CASES.cases[0],
        ca_id: 'CA-C',
        ho_ten: 'An Văn C',
        ngay_sinh: '1950-01-02',
        chan_doan_chinh: 'Hen phế quản',
      },
    ]

    expect(sortOrders(rowsWithDemographics, 'nguoi_benh', 'asc').map((r) => r.ca_id)).toEqual([
      'CA-C',
      'CA-A',
      'CA-B',
    ])
    expect(sortOrders(rowsWithDemographics, 'ngay_sinh', 'asc').map((r) => r.ca_id)).toEqual([
      'CA-C',
      'CA-A',
      'CA-B',
    ])
    expect(sortOrders(rowsWithDemographics, 'ngay_sinh', 'desc').map((r) => r.ca_id)).toEqual([
      'CA-A',
      'CA-C',
      'CA-B',
    ])
    expect(sortOrders(rowsWithDemographics, 'chan_doan_chinh', 'asc').map((r) => r.ca_id)).toEqual([
      'CA-C',
      'CA-A',
      'CA-B',
    ])

    const byFormattedDob = filterOrders(rowsWithDemographics, all, '12/05/1980')
    expect(byFormattedDob.map((r) => r.ca_id)).toEqual(['CA-A'])
  })
})

describe('hàm thuần phân trang 30 dòng và tham số URL ?trang=', () => {
  it('cắt 67 mục thành 3 trang: 30, 30, 7 và kẹp trang ngoài biên', () => {
    const items = Array.from({ length: 67 }, (_, i) => i + 1)
    expect(DEFAULT_PAGE_SIZE).toBe(30)

    const p1 = paginateItems(items, 1)
    expect(p1.items).toHaveLength(30)
    expect(p1.startIndex).toBe(1)
    expect(p1.endIndex).toBe(30)
    expect(p1.totalPages).toBe(3)

    const p3 = paginateItems(items, 3)
    expect(p3.items).toHaveLength(7)
    expect(p3.startIndex).toBe(61)
    expect(p3.endIndex).toBe(67)

    const clamped = paginateItems(items, 99)
    expect(clamped.currentPage).toBe(3)
    expect(clamped.items).toHaveLength(7)

    const empty = paginateItems([], 2)
    expect(empty).toMatchObject({
      items: [],
      currentPage: 1,
      totalPages: 1,
      totalItems: 0,
      startIndex: 0,
      endIndex: 0,
    })
  })

  it('đọc và ghi tham số ?trang= hợp lệ, bỏ qua trang 1 và chuỗi sai', () => {
    expect(parsePageParam(null)).toBe(1)
    expect(parsePageParam('0')).toBe(1)
    expect(parsePageParam('-2')).toBe(1)
    expect(parsePageParam('2abc')).toBe(1)
    expect(parsePageParam('2')).toBe(2)

    const p2 = updatePageInSearchParams(new URLSearchParams('tab=x'), 2)
    expect(p2.toString()).toBe('tab=x&trang=2')
    const p1 = updatePageInSearchParams(p2, 1)
    expect(p1.toString()).toBe('tab=x')

    expect(getVisiblePageNumbers(1, 3)).toEqual([1, 2, 3])
    expect(getVisiblePageNumbers(5, 10)).toEqual([1, 'ellipsis', 4, 5, 6, 'ellipsis', 10])
  })
})
