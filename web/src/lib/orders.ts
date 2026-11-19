import type { DongHangDoi } from '../api/types.ts'
import { formatIsoTimestamp } from './displayFormat.ts'

export type OrderFilterGroup = 'tat_ca' | 'can_xem' | 'thieu_du_lieu' | 'dat' | 'da_phan_hoi'

export type OrderSelectionFilter =
  | { type: 'group'; group: OrderFilterGroup }
  | { type: 'khoa'; khoa: string }

export type OrderSortField =
  | 'ket_qua'
  | 'uu_tien'
  | 'thoi_diem_ke'
  | 'thoi_diem_ke_xa_nhat'
  | 'thoi_diem_ke_gan_nhat'
  | 'ma_y_lenh'
  | 'ca_id'
  | 'ma_bn'
  | 'ho_ten'
  | 'nguoi_benh'
  | 'khoa'
  | 'chan_doan'
  | 'so_don_cho'
  | 'trang_thai'

export type OrderSortDirection = 'asc' | 'desc'

export type OrderPriorityLevel = 'cao' | 'trung_binh' | 'thap'

export type OrderWorkflowStatus = 'chua_duyet' | 'dang_cho' | 'da_huy' | 'da_xong'

export type LegacyOrderWorkflowStatus = OrderWorkflowStatus | 'da_duyet'

export type OrderAiWarningFilter =
  | 'nghiem_trong'
  | 'can_luu_y'
  | 'thieu_du_lieu'
  | 'ngoai_hdsd'
  | 'dat'

export type OrderRowInput = DongHangDoi & {
  trang_thai_y_lenh?: LegacyOrderWorkflowStatus | null
}

type OrderFilterValues<T extends string> = T | readonly T[] | 'all'

export interface OrderColumnFilters {
  priority?: OrderFilterValues<OrderPriorityLevel>
  khoa?: OrderFilterValues<string>
  status?: OrderFilterValues<OrderWorkflowStatus>
  aiWarning?: OrderFilterValues<OrderAiWarningFilter>
  timeText?: string
  dateExact?: string
}

/** Chuẩn hoá bộ lọc cũ và mới; không có lựa chọn nghĩa là tất cả. */
export function selectedFilterValues<T extends string>(value: OrderFilterValues<T> | undefined): readonly T[] {
  if (value === undefined || value === 'all' || value === '') return []
  return typeof value === 'string' ? [value] : value
}

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
  tat_ca: 'Tất cả người bệnh',
  can_xem: 'Cần xem',
  thieu_du_lieu: 'Thiếu dữ liệu',
  dat: 'Đạt',
  da_phan_hoi: 'Đã phản hồi',
}

export const ORDER_PRIORITY_LABELS: Record<OrderPriorityLevel, string> = {
  cao: 'Cao',
  trung_binh: 'Trung bình',
  thap: 'Thấp',
}

export const ORDER_STATUS_LABELS: Record<OrderWorkflowStatus, string> = {
  chua_duyet: 'Chưa duyệt',
  dang_cho: 'Đang chờ',
  da_huy: 'Đã hủy',
  da_xong: 'Đã xong',
}

export const ORDER_AI_WARNING_LABELS: Record<OrderAiWarningFilter, string> = {
  nghiem_trong: 'Nghiêm trọng',
  can_luu_y: 'Cần lưu ý',
  thieu_du_lieu: 'Thiếu dữ liệu',
  ngoai_hdsd: 'Ngoài HDSD',
  dat: 'Đạt',
}

const VI_COLLATOR = new Intl.Collator('vi', { numeric: true, sensitivity: 'base' })

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

/** Xác định mức độ ưu tiên hiển thị trên bảng từ trường `uu_tien` (0..4). */
export function getOrderPriorityLevel(item: Pick<DongHangDoi, 'uu_tien'>): OrderPriorityLevel {
  if (item.uu_tien === 0) {
    return 'cao'
  }
  if (item.uu_tien === 1 || item.uu_tien === 2) {
    return 'trung_binh'
  }
  return 'thap'
}

/** Chuẩn hoá trạng thái đơn về 4 giá trị chuẩn của người bệnh. */
export function normalizeWorkflowStatus(status: LegacyOrderWorkflowStatus): OrderWorkflowStatus {
  return status === 'da_duyet' ? 'da_xong' : status
}

/** Xác định trạng thái người bệnh theo thứ tự ưu tiên: Chưa duyệt > Đang chờ > Đã hủy > Đã xong. */
export function getOrderWorkflowStatus(item: OrderRowInput): OrderWorkflowStatus {
  if (item.trang_thai_y_lenh) {
    return normalizeWorkflowStatus(item.trang_thai_y_lenh)
  }
  if (item.da_phan_hoi_het && (item.so_don_cho ?? 1) <= 1) {
    return 'da_xong'
  }
  if (item.trang_thai_nb) {
    return item.trang_thai_nb
  }
  if (item.da_phan_hoi_het) {
    return 'da_xong'
  }
  if (item.so_thieu_du_lieu > 0) {
    return 'dang_cho'
  }
  return 'chua_duyet'
}

/** Lấy thời điểm kê xa nhất (đơn chờ lâu nhất) của người bệnh. */
export function getOldestPendingTime(item: DongHangDoi): string | null {
  return item.thoi_diem_ke_xa_nhat ?? item.thoi_diem_ke ?? null
}

/** Lấy thời điểm kê gần nhất (đơn chờ mới nhất) của người bệnh. */
export function getLatestPendingTime(item: DongHangDoi): string | null {
  return item.thoi_diem_ke_gan_nhat ?? item.thoi_diem_ke ?? null
}

/** Lấy số đơn đang chờ duyệt của người bệnh. */
export function getPendingOrderCount(item: DongHangDoi): number {
  if (typeof item.so_don_cho === 'number' && Number.isFinite(item.so_don_cho)) {
    return item.so_don_cho
  }
  return item.da_phan_hoi_het ? 0 : 1
}

/** Ghép toàn bộ chẩn đoán kèm mã ICD-10 tương ứng để hiển thị và tìm kiếm. */
export function formatDiagnosesWithIcd(item: DongHangDoi): string {
  if (item.chan_doan && item.chan_doan.length > 0) {
    return item.chan_doan
      .map((diag) => (diag.ma_icd10 ? `${diag.noi_dung} (${diag.ma_icd10})` : diag.noi_dung))
      .join('; ')
  }
  return item.chan_doan_chinh?.trim() ?? ''
}

/** Phân loại nhóm cảnh báo AI chính của dòng y lệnh. */
export function getOrderAiWarningKind(item: DongHangDoi): OrderAiWarningFilter {
  if (item.so_nghiem_trong > 0) {
    return 'nghiem_trong'
  }
  if (item.so_can_luu_y > 0) {
    return 'can_luu_y'
  }
  if (item.so_thieu_du_lieu > 0) {
    return 'thieu_du_lieu'
  }
  if (item.uu_tien === 2) {
    return 'ngoai_hdsd'
  }
  return 'dat'
}

/** Tạo nội dung chú giải khi di chuột vào biểu tượng cảnh báo AI. */
export function getOrderAiWarningTooltip(item: DongHangDoi): string {
  if (item.so_nghiem_trong > 0) {
    return `${item.so_nghiem_trong} nghiêm trọng — ${item.mo_ta}`
  }
  if (item.so_can_luu_y > 0) {
    return `${item.so_can_luu_y} cần lưu ý — ${item.mo_ta}`
  }
  if (item.so_thieu_du_lieu > 0) {
    return `Thiếu dữ liệu (${item.so_thieu_du_lieu}) — ${item.mo_ta}`
  }
  if (item.uu_tien === 2) {
    return `Ngoài HDSD — ${item.mo_ta}`
  }
  return `Đạt — ${item.mo_ta}`
}

/** Lấy mã bệnh nhân; ưu tiên `nguoi_benh_id` thật từ hệ thống, dự phòng `NB-{ca_id}`. */
export function getOrderPatientCode(item: DongHangDoi): string {
  if (item.nguoi_benh_id && item.nguoi_benh_id.trim()) {
    return item.nguoi_benh_id.trim()
  }
  if (!item.nguoi_benh_tom_tat || !item.nguoi_benh_tom_tat.trim()) {
    return ''
  }
  return `NB-${item.ca_id}`
}

/** Trích ngày YYYY-MM-DD (theo múi giờ Việt Nam +07:00) từ chuỗi thời điểm kê để đối chiếu lịch. */
export function extractOrderDateYmd(raw: string | null | undefined): string {
  if (!raw) {
    return ''
  }
  const formatted = formatIsoTimestamp(raw.trim())
  const dmyMatch = /(\d{2})\/(\d{2})\/(\d{4})/.exec(formatted)
  if (dmyMatch) {
    const [, dd, mm, yyyy] = dmyMatch
    return `${yyyy}-${mm}-${dd}`
  }
  const ymdMatch = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw.trim())
  return ymdMatch ? `${ymdMatch[1]}-${ymdMatch[2]}-${ymdMatch[3]}` : ''
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
export function countOrderGroups(
  cases: readonly OrderRowInput[],
  columnFilters?: OrderColumnFilters,
): OrderGroupCounts {
  const matching = columnFilters ? applyOrderColumnFilters(cases, columnFilters) : cases
  let canXem = 0
  let thieuDuLieu = 0
  let dat = 0
  let daPhanHoi = 0
  const deptMap = new Map<string, number>()

  for (const item of matching) {
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
    .sort((a, b) => VI_COLLATOR.compare(a.khoa, b.khoa))

  return {
    tat_ca: matching.length,
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
    getOrderPatientCode(item),
    item.nguoi_benh_tom_tat ?? '',
    item.ho_ten ?? '',
    item.ngay_sinh ?? '',
    item.chan_doan_chinh ?? '',
    formatDiagnosesWithIcd(item),
    item.khoa,
    ...(item.thuoc ?? []),
    item.mo_ta,
    item.huy_hieu,
    ORDER_STATUS_LABELS[getOrderWorkflowStatus(item)],
  ]
    .map(normalizeVietnameseSearch)
    .join(' ')

  const tokens = normalizedQuery.split(/\s+/).filter(Boolean)
  return tokens.every((token) => haystack.includes(token))
}

/** Lọc thêm theo các bộ lọc trên từng cột (Ưu tiên, Thời điểm kê, Khoa, Trạng thái, Cảnh báo AI). */
export function applyOrderColumnFilters<T extends OrderRowInput>(
  cases: readonly T[],
  columnFilters?: OrderColumnFilters,
): T[] {
  if (!columnFilters) {
    return [...cases]
  }
  const { priority, khoa, status, aiWarning, timeText, dateExact } = columnFilters
  const priorities = selectedFilterValues(priority)
  const departments = selectedFilterValues(khoa)
  const statuses = selectedFilterValues(status)
  const warnings = selectedFilterValues(aiWarning)
  const normTimeText = timeText ? timeText.trim().toLowerCase() : ''
  const normDateExact = dateExact ? dateExact.trim() : ''

  return cases.filter((item) => {
    if (priorities.length && !priorities.includes(getOrderPriorityLevel(item))) {
      return false
    }
    if (departments.length && !departments.includes(item.khoa)) {
      return false
    }
    if (statuses.length && !statuses.includes(getOrderWorkflowStatus(item))) {
      return false
    }
    if (warnings.length && !warnings.includes(getOrderAiWarningKind(item))) {
      return false
    }
    if (normDateExact) {
      const oldestYmd = extractOrderDateYmd(getOldestPendingTime(item))
      const latestYmd = extractOrderDateYmd(getLatestPendingTime(item))
      if (oldestYmd !== normDateExact && latestYmd !== normDateExact) {
        return false
      }
    }
    if (normTimeText) {
      const candidates = [getOldestPendingTime(item), getLatestPendingTime(item), item.thoi_diem_ke]
        .filter((v): v is string => Boolean(v))
      const combined = candidates
        .map((rawTime) => `${rawTime} ${formatIsoTimestamp(rawTime)} ${extractOrderDateYmd(rawTime)}`)
        .join(' ')
        .toLowerCase()
      if (!combined.includes(normTimeText)) {
        return false
      }
    }
    return true
  })
}

/** Lọc danh sách y lệnh theo nhóm thanh bên/khoa và từ khoá tìm kiếm không phân biệt dấu. */
export function filterOrders<T extends OrderRowInput>(
  cases: readonly T[],
  filter: OrderSelectionFilter,
  searchQuery = '',
  columnFilters?: OrderColumnFilters,
): T[] {
  const normalizedQuery = normalizeVietnameseSearch(searchQuery)
  const baseFiltered = cases.filter(
    (item) => matchesSelectionFilter(item, filter) && matchesSearchQuery(item, normalizedQuery),
  )
  return applyOrderColumnFilters(baseFiltered, columnFilters)
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

const STATUS_SORT_RANK: Record<OrderWorkflowStatus, number> = {
  chua_duyet: 0,
  dang_cho: 1,
  da_huy: 2,
  da_xong: 3,
}

/**
 * Sắp xếp danh sách người bệnh ổn định trên mọi cột bằng Intl.Collator và mốc thời gian số.
 */
export function sortOrders<T extends OrderRowInput>(
  cases: readonly T[],
  sortField: OrderSortField = 'ket_qua',
  sortDirection: OrderSortDirection = 'desc',
): T[] {
  const indexed = cases.map((item, idx) => ({ item, idx }))

  indexed.sort((a, b) => {
    let cmp = 0
    if (sortField === 'ket_qua' || sortField === 'uu_tien') {
      const severityDiff = a.item.uu_tien - b.item.uu_tien
      cmp = sortDirection === 'desc' ? severityDiff : -severityDiff
      if (cmp === 0) {
        cmp = compareTimes(getOldestPendingTime(a.item), getOldestPendingTime(b.item))
      }
    } else if (sortField === 'thoi_diem_ke' || sortField === 'thoi_diem_ke_xa_nhat') {
      const timeDiff = compareTimes(getOldestPendingTime(a.item), getOldestPendingTime(b.item))
      cmp = sortDirection === 'asc' ? timeDiff : -timeDiff
      if (cmp === 0) {
        cmp = a.item.uu_tien - b.item.uu_tien
      }
    } else if (sortField === 'thoi_diem_ke_gan_nhat') {
      const timeDiff = compareTimes(getLatestPendingTime(a.item), getLatestPendingTime(b.item))
      cmp = sortDirection === 'asc' ? timeDiff : -timeDiff
      if (cmp === 0) {
        cmp = a.item.uu_tien - b.item.uu_tien
      }
    } else if (sortField === 'ma_y_lenh') {
      const aCode = a.item.ma_y_lenh ?? a.item.ca_id
      const bCode = b.item.ma_y_lenh ?? b.item.ca_id
      const diff = VI_COLLATOR.compare(aCode, bCode)
      cmp = sortDirection === 'asc' ? diff : -diff
    } else if (sortField === 'ma_bn') {
      const diff = VI_COLLATOR.compare(getOrderPatientCode(a.item), getOrderPatientCode(b.item))
      cmp = sortDirection === 'asc' ? diff : -diff
    } else if (sortField === 'ho_ten') {
      const diff = VI_COLLATOR.compare(a.item.ho_ten ?? '', b.item.ho_ten ?? '')
      cmp = sortDirection === 'asc' ? diff : -diff
    } else if (sortField === 'nguoi_benh') {
      const diff = VI_COLLATOR.compare(
        a.item.nguoi_benh_tom_tat ?? '',
        b.item.nguoi_benh_tom_tat ?? '',
      )
      cmp = sortDirection === 'asc' ? diff : -diff
    } else if (sortField === 'khoa') {
      const diff = VI_COLLATOR.compare(a.item.khoa, b.item.khoa)
      cmp = sortDirection === 'asc' ? diff : -diff
    } else if (sortField === 'chan_doan') {
      const diff = VI_COLLATOR.compare(
        formatDiagnosesWithIcd(a.item),
        formatDiagnosesWithIcd(b.item),
      )
      cmp = sortDirection === 'asc' ? diff : -diff
    } else if (sortField === 'so_don_cho') {
      const diff = getPendingOrderCount(a.item) - getPendingOrderCount(b.item)
      cmp = sortDirection === 'asc' ? diff : -diff
    } else if (sortField === 'trang_thai') {
      const diff =
        STATUS_SORT_RANK[getOrderWorkflowStatus(a.item)] -
        STATUS_SORT_RANK[getOrderWorkflowStatus(b.item)]
      cmp = sortDirection === 'asc' ? diff : -diff
    } else {
      const idDiff = VI_COLLATOR.compare(a.item.ca_id, b.item.ca_id)
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
