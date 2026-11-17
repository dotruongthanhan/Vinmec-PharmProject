import type { DongHangDoi } from '../api/types.ts'

export type OrderFilterGroup = 'tat_ca' | 'can_xem' | 'thieu_du_lieu' | 'dat' | 'da_phan_hoi'

export type OrderSelectionFilter =
  | { type: 'group'; group: OrderFilterGroup }
  | { type: 'khoa'; khoa: string }

export type OrderSortField = 'ket_qua' | 'thoi_diem_ke' | 'ca_id'
export type OrderSortDirection = 'asc' | 'desc'

export type OrderRowInput = DongHangDoi

export interface DepartmentCount {
  khoa: string
  count: number
}

export interface OrderGroupCounts {
  tat_ca: number
  can_xem: number
  thieu_du_lieu: number
  dat: number
  da_phan_hoi: number
  departments: DepartmentCount[]
}

export const ORDER_FILTER_LABELS: Record<OrderFilterGroup, string> = {
  tat_ca: 'Tất cả y lệnh',
  can_xem: 'Cần xem',
  thieu_du_lieu: 'Thiếu dữ liệu',
  dat: 'Đạt',
  da_phan_hoi: 'Đã phản hồi',
}

/** Chuẩn hoá chuỗi tiếng Việt (bỏ dấu, chữ thường) phục vụ tìm kiếm không phân biệt hoa thường và dấu. */
export function normalizeVietnameseSearch(raw: string): string {
  return raw
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim()
}

/** Kiểm tra một dòng y lệnh có thuộc nhóm "Cần xem" (có nhận định nghiêm trọng hoặc cần lưu ý). */
export function isNeedsReviewOrder(item: DongHangDoi): boolean {
  return item.so_nghiem_trong > 0 || item.so_can_luu_y > 0
}

/** Kiểm tra một dòng y lệnh có thuộc nhóm "Thiếu dữ liệu". */
export function isMissingDataOrder(item: DongHangDoi): boolean {
  return item.so_thieu_du_lieu > 0
}

/** Kiểm tra một dòng y lệnh có thuộc nhóm "Đạt" (không có cảnh báo hay thiếu dữ liệu). */
export function isPassedOrder(item: DongHangDoi): boolean {
  return (
    item.so_nghiem_trong === 0 &&
    item.so_can_luu_y === 0 &&
    item.so_thieu_du_lieu === 0 &&
    item.uu_tien === 4
  )
}

/** Tính số đếm thật cho các nhóm ở thanh bên và danh sách khoa từ dữ liệu /api/cases. */
export function countOrderGroups(cases: readonly DongHangDoi[]): OrderGroupCounts {
  let canXem = 0
  let thieuDuLieu = 0
  let dat = 0
  let daPhanHoi = 0
  const deptMap = new Map<string, number>()

  for (const item of cases) {
    if (isNeedsReviewOrder(item)) {
      canXem += 1
    }
    if (isMissingDataOrder(item)) {
      thieuDuLieu += 1
    }
    if (isPassedOrder(item)) {
      dat += 1
    }
    if (item.da_phan_hoi_het) {
      daPhanHoi += 1
    }
    deptMap.set(item.khoa, (deptMap.get(item.khoa) ?? 0) + 1)
  }

  const departments: DepartmentCount[] = Array.from(deptMap.entries())
    .map(([khoa, count]) => ({ khoa, count }))
    .sort((a, b) => a.khoa.localeCompare(b.khoa, 'vi'))

  return {
    tat_ca: cases.length,
    can_xem: canXem,
    thieu_du_lieu: thieuDuLieu,
    dat,
    da_phan_hoi: daPhanHoi,
    departments,
  }
}

function matchesSelectionFilter(
  item: DongHangDoi,
  filter: OrderSelectionFilter,
): boolean {
  if (filter.type === 'khoa') {
    return item.khoa === filter.khoa
  }
  switch (filter.group) {
    case 'tat_ca':
      return true
    case 'can_xem':
      return isNeedsReviewOrder(item)
    case 'thieu_du_lieu':
      return isMissingDataOrder(item)
    case 'dat':
      return isPassedOrder(item)
    case 'da_phan_hoi':
      return item.da_phan_hoi_het
  }
}

function matchesSearchQuery(item: OrderRowInput, normalizedQuery: string): boolean {
  if (!normalizedQuery) {
    return true
  }
  const haystack = [
    item.ca_id,
    item.ma_y_lenh ?? '',
    item.khoa,
    ...(item.thuoc ?? []),
    item.mo_ta,
    item.huy_hieu,
  ]
    .map(normalizeVietnameseSearch)
    .join(' ')

  const tokens = normalizedQuery.split(/\s+/).filter(Boolean)
  return tokens.every((token) => haystack.includes(token))
}

/** Lọc danh sách y lệnh theo nhóm thanh bên/khoa và từ khoá tìm kiếm không phân biệt dấu. */
export function filterOrders<T extends OrderRowInput>(
  cases: readonly T[],
  filter: OrderSelectionFilter,
  searchQuery = '',
): T[] {
  const normalizedQuery = normalizeVietnameseSearch(searchQuery)
  return cases.filter(
    (item) => matchesSelectionFilter(item, filter) && matchesSearchQuery(item, normalizedQuery),
  )
}

function parseSortableTimeMs(raw: string | null | undefined): number | null {
  if (!raw) {
    return null
  }
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }
  const isoMs = Date.parse(trimmed)
  if (Number.isFinite(isoMs)) {
    return isoMs
  }
  const dmyMatch = /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})$/.exec(trimmed)
  if (dmyMatch) {
    const [, dd, mm, yyyy, hh, min] = dmyMatch
    return Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(min))
  }
  const hmDmyMatch = /^(\d{2}):(\d{2})\s*·\s*(\d{2})\/(\d{2})\/(\d{4})$/.exec(trimmed)
  if (hmDmyMatch) {
    const [, hh, min, dd, mm, yyyy] = hmDmyMatch
    return Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(min))
  }
  return null
}

function compareTimes(aTime: string | null | undefined, bTime: string | null | undefined): number {
  const aMs = parseSortableTimeMs(aTime)
  const bMs = parseSortableTimeMs(bTime)
  if (aMs !== null && bMs !== null) {
    return aMs - bMs
  }
  if (aMs !== null) {
    return -1
  }
  if (bMs !== null) {
    return 1
  }
  return 0
}

/**
 * Sắp xếp danh sách y lệnh ổn định:
 * - Mặc định (`ket_qua`, `desc`): mức nghiêm trọng giảm dần (`uu_tien` 0 → 4), rồi thời điểm kê tăng dần.
 * - `ket_qua`, `asc`: mức nghiêm trọng tăng dần (`uu_tien` 4 → 0).
 * - `thoi_diem_ke`: theo thời điểm kê, sau đó đến mức độ.
 */
export function sortOrders<T extends OrderRowInput>(
  cases: readonly T[],
  sortField: OrderSortField = 'ket_qua',
  sortDirection: OrderSortDirection = 'desc',
): T[] {
  const indexed = cases.map((item, idx) => ({ item, idx }))

  indexed.sort((a, b) => {
    let cmp = 0
    if (sortField === 'ket_qua') {
      const severityDiff = a.item.uu_tien - b.item.uu_tien
      cmp = sortDirection === 'desc' ? severityDiff : -severityDiff
      if (cmp === 0) {
        cmp = compareTimes(a.item.thoi_diem_ke, b.item.thoi_diem_ke)
      }
    } else if (sortField === 'thoi_diem_ke') {
      const timeDiff = compareTimes(a.item.thoi_diem_ke, b.item.thoi_diem_ke)
      cmp = sortDirection === 'asc' ? timeDiff : -timeDiff
      if (cmp === 0) {
        cmp = a.item.uu_tien - b.item.uu_tien
      }
    } else {
      const idDiff = a.item.ca_id.localeCompare(b.item.ca_id, 'vi')
      cmp = sortDirection === 'asc' ? idDiff : -idDiff
    }

    if (cmp !== 0) {
      return cmp
    }
    return a.idx - b.idx
  })

  return indexed.map((entry) => entry.item)
}

/** Lấy mã ca kế tiếp/trước đó khi điều hướng bằng phím mũi tên trong bảng y lệnh. */
export function stepOrderSelection(
  cases: readonly DongHangDoi[],
  currentId: string | null,
  direction: 'up' | 'down',
): string | null {
  if (cases.length === 0) {
    return null
  }
  if (currentId === null) {
    return direction === 'up' ? cases[cases.length - 1].ca_id : cases[0].ca_id
  }
  const idx = cases.findIndex((item) => item.ca_id === currentId)
  if (idx === -1) {
    return cases[0].ca_id
  }
  const nextIdx =
    direction === 'down' ? Math.min(idx + 1, cases.length - 1) : Math.max(idx - 1, 0)
  return cases[nextIdx].ca_id
}

/** Lấy tiêu đề hiển thị cho bộ lọc hiện tại trên vùng giữa. */
export function getOrderFilterTitle(filter: OrderSelectionFilter): string {
  if (filter.type === 'khoa') {
    return `Khoa ${filter.khoa}`
  }
  return ORDER_FILTER_LABELS[filter.group]
}
