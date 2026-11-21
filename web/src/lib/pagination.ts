export const DEFAULT_PAGE_SIZE = 30

export interface PaginationMeta<T> {
  items: T[]
  currentPage: number
  totalPages: number
  totalItems: number
  pageSize: number
  startIndex: number
  endIndex: number
}

/** Đọc số trang hợp lệ (>= 1) từ tham số truy vấn `?trang=`. */
export function parsePageParam(raw: string | null | undefined): number {
  if (!raw) {
    return 1
  }
  const trimmed = raw.trim()
  if (!/^\d+$/.test(trimmed)) {
    return 1
  }
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1
}

/** Cập nhật tham số `?trang=` trên URLSearchParams; trang 1 được bỏ khỏi URL. */
export function updatePageInSearchParams(
  previous: URLSearchParams,
  page: number,
): URLSearchParams {
  const next = new URLSearchParams(previous)
  const normalized = Number.isFinite(page) ? Math.max(1, Math.floor(page)) : 1
  if (normalized <= 1) {
    next.delete('trang')
  } else {
    next.set('trang', String(normalized))
  }
  return next
}

/** Cắt lát một trang dữ liệu sau khi đã lọc và sắp xếp toàn bộ danh sách. */
export function paginateItems<T>(
  items: readonly T[],
  page: number,
  pageSize: number = DEFAULT_PAGE_SIZE,
): PaginationMeta<T> {
  const safePageSize =
    Number.isFinite(pageSize) && pageSize >= 1 ? Math.floor(pageSize) : DEFAULT_PAGE_SIZE
  const totalItems = items.length
  const totalPages = Math.max(1, Math.ceil(totalItems / safePageSize))
  const requested = Number.isFinite(page) ? Math.floor(page) : 1
  const currentPage = Math.min(Math.max(1, requested), totalPages)

  if (totalItems === 0) {
    return {
      items: [],
      currentPage: 1,
      totalPages: 1,
      totalItems: 0,
      pageSize: safePageSize,
      startIndex: 0,
      endIndex: 0,
    }
  }

  const offset = (currentPage - 1) * safePageSize
  const sliced = items.slice(offset, offset + safePageSize)
  return {
    items: sliced,
    currentPage,
    totalPages,
    totalItems,
    pageSize: safePageSize,
    startIndex: offset + 1,
    endIndex: offset + sliced.length,
  }
}

/** Tạo danh sách số trang hiển thị kèm dấu ba chấm khi tổng số trang lớn. */
export function getVisiblePageNumbers(
  currentPage: number,
  totalPages: number,
): (number | 'ellipsis')[] {
  if (totalPages <= 1) {
    return [1]
  }
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, idx) => idx + 1)
  }

  const pages = new Set<number>([1, totalPages])
  for (let p = currentPage - 1; p <= currentPage + 1; p += 1) {
    if (p >= 1 && p <= totalPages) {
      pages.add(p)
    }
  }
  if (currentPage <= 3) {
    pages.add(2)
    pages.add(3)
    pages.add(4)
  }
  if (currentPage >= totalPages - 2) {
    pages.add(totalPages - 3)
    pages.add(totalPages - 2)
    pages.add(totalPages - 1)
  }

  const sorted = Array.from(pages)
    .filter((p) => p >= 1 && p <= totalPages)
    .sort((a, b) => a - b)

  const result: (number | 'ellipsis')[] = []
  for (let i = 0; i < sorted.length; i += 1) {
    const val = sorted[i]
    if (i > 0) {
      const gap = val - sorted[i - 1]
      if (gap === 2) {
        result.push(val - 1)
      } else if (gap > 2) {
        result.push('ellipsis')
      }
    }
    result.push(val)
  }
  return result
}
