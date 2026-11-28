import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getVisiblePageNumbers } from '@/lib/pagination'

export interface TablePaginationProps {
  currentPage: number
  totalPages: number
  totalItems: number
  startIndex: number
  endIndex: number
  onPageChange: (page: number) => void
}

/** Thanh phân trang chuẩn phía dưới bảng danh sách (khoảng dòng, Trước / Sau, số trang). */
export function TablePagination({
  currentPage,
  totalPages,
  totalItems,
  startIndex,
  endIndex,
  onPageChange,
}: TablePaginationProps) {
  if (totalItems === 0) {
    return null
  }

  const pages = getVisiblePageNumbers(currentPage, totalPages)

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs text-fg-subtle">
      <p className="font-mono tabular-nums" aria-live="polite">
        {`${startIndex}\u2013${endIndex} / ${totalItems}`}
      </p>

      <nav aria-label="Phân trang" className="flex flex-wrap items-center gap-1">
        <Button
          variant="secondary"
          size="sm"
          disabled={currentPage <= 1}
          aria-label="Trang trước"
          iconLeft={<ChevronLeft className="size-3.5" strokeWidth={1.75} />}
          onClick={() => onPageChange(currentPage - 1)}
        >
          Trước
        </Button>

        {pages.map((entry, idx) =>
          entry === 'ellipsis' ? (
            <span
              key={`ellipsis-${idx}`}
              aria-hidden="true"
              className="px-1.5 text-xs text-fg-subtle select-none"
            >
              …
            </span>
          ) : (
            <Button
              key={entry}
              variant={entry === currentPage ? 'primary' : 'secondary'}
              size="sm"
              aria-label={`Trang ${entry}`}
              aria-current={entry === currentPage ? 'page' : undefined}
              onClick={() => onPageChange(entry)}
              className="min-w-7 px-2 tabular-nums"
            >
              {entry}
            </Button>
          ),
        )}

        <Button
          variant="secondary"
          size="sm"
          disabled={currentPage >= totalPages}
          aria-label="Trang sau"
          onClick={() => onPageChange(currentPage + 1)}
        >
          <span>Sau</span>
          <ChevronRight className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
        </Button>
      </nav>
    </div>
  )
}
