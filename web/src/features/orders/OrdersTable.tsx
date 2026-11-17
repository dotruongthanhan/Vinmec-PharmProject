import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckCheck,
  CircleCheck,
  CircleHelp,
  ClipboardList,
  FileQuestion,
  OctagonAlert,
  TriangleAlert,
} from 'lucide-react'
import { useRef } from 'react'
import type { KeyboardEvent } from 'react'
import type { DongHangDoi, LoiNapCa } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/features/states/StateViews'
import { cn } from '@/lib/cn'
import { formatReadableDateTime } from '@/lib/displayFormat'
import {
  stepOrderSelection,
} from '@/lib/orders'
import type {
  OrderSortDirection,
  OrderSortField,
} from '@/lib/orders'

export interface OrdersTableProps {
  filterTitle: string
  orders: readonly DongHangDoi[]
  totalCount: number
  loiNap: readonly LoiNapCa[]
  loading: boolean
  error: string | null
  searchQuery: string
  sortField: OrderSortField
  sortDirection: OrderSortDirection
  onToggleSort: (field: OrderSortField) => void
  onOpenOrder: (caId: string) => void
  onResetFilters: () => void
  onRetry: () => void
}

const PRIORITY_DOT_CLASS: Record<DongHangDoi['uu_tien'], string> = {
  0: 'bg-danger-solid',
  1: 'bg-warning-solid',
  2: 'bg-offlabel-solid',
  3: 'bg-missing-solid',
  4: 'bg-success-solid',
}

const PRIORITY_SR_LABEL: Record<DongHangDoi['uu_tien'], string> = {
  0: 'Mức nghiêm trọng',
  1: 'Mức cần lưu ý',
  2: 'Ngoài HDSD',
  3: 'Thiếu dữ liệu',
  4: 'Đạt',
}

function ResultBadges({ item }: { item: DongHangDoi }) {
  const className = 'gap-1 px-1 tabular-nums'
  if (item.so_nghiem_trong > 0) {
    return <Badge tone="danger" className={className} icon={<OctagonAlert />}>{item.so_nghiem_trong} nghiêm trọng</Badge>
  }
  if (item.so_can_luu_y > 0) {
    return <Badge tone="warning" className={className} icon={<TriangleAlert />}>{item.so_can_luu_y} cần lưu ý</Badge>
  }
  if (item.so_thieu_du_lieu > 0) {
    return <Badge tone="missing" className={className} icon={<CircleHelp />}>Thiếu dữ liệu</Badge>
  }
  if (item.uu_tien === 2) {
    return <Badge tone="offlabel" className={className} icon={<FileQuestion />}>Ngoài HDSD</Badge>
  }
  return <Badge tone="success" className={className} icon={<CircleCheck />}>Đạt</Badge>
}

/** Danh sách y lệnh dạng bảng dày (44 px mỗi dòng), hỗ trợ sắp xếp và điều hướng bàn phím. */
export function OrdersTable({
  filterTitle,
  orders,
  totalCount,
  loiNap,
  loading,
  error,
  searchQuery,
  sortField,
  sortDirection,
  onToggleSort,
  onOpenOrder,
  onResetFilters,
  onRetry,
}: OrdersTableProps) {
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({})

  const handleRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, caId: string) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      onOpenOrder(caId)
      return
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
      return
    }
    const direction = event.key === 'ArrowDown' ? 'down' : 'up'
    const nextId = stepOrderSelection(orders, caId, direction)
    if (!nextId) {
      return
    }
    event.preventDefault()
    const targetRow = rowRefs.current[nextId]
    if (targetRow) {
      targetRow.focus()
      targetRow.scrollIntoView({ block: 'nearest' })
    }
  }

  const isResultSorted = sortField === 'ket_qua'
  const SortIcon = !isResultSorted
    ? ArrowUpDown
    : sortDirection === 'desc'
      ? ArrowDown
      : ArrowUp

  return (
    <div className="orders-panel flex min-w-0 flex-col gap-3">
      {/* Đầu trang danh sách: tên bộ lọc và số y lệnh */}
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="font-serif text-[24px] leading-[32px] font-normal text-fg">
            {filterTitle}
          </h1>
          <span className="font-mono text-xs text-fg-subtle tabular-nums">
            {loading ? 'Đang tải…' : `${orders.length} y lệnh`}
          </span>
          {searchQuery.trim() ? (
            <span className="text-xs text-fg-muted">
              Lọc theo &ldquo;{searchQuery.trim()}&rdquo;
            </span>
          ) : null}
        </div>

        {(searchQuery.trim() || orders.length !== totalCount) && !loading ? (
          <Button variant="ghost" size="sm" onClick={onResetFilters}>
            Hiện tất cả ({totalCount})
          </Button>
        ) : null}
      </div>

      {loiNap.length > 0 ? (
        <div className="flex flex-col gap-2" role="alert" aria-label="Tệp ca bệnh bị lỗi">
          {loiNap.map((errItem, idx) => (
            <InlineAlert
              key={`${errItem.tep}-${idx}`}
              tone="danger"
              title={`Lỗi tệp: ${errItem.tep}`}
            >
              <span className="whitespace-pre-wrap break-words text-xs">{errItem.loi}</span>
            </InlineAlert>
          ))}
        </div>
      ) : null}

      {loading ? (
        <div
          className="overflow-hidden rounded-md border border-line bg-surface"
          aria-busy="true"
          aria-label="Đang tải danh sách y lệnh"
        >
          <div className="h-9 border-b border-line bg-surface-muted px-3 flex items-center">
            <Skeleton className="h-3 w-48" />
          </div>
          {Array.from({ length: 6 }).map((_, idx) => (
            <div
              key={idx}
              className="h-[44px] border-b border-line last:border-b-0 px-3 flex items-center gap-4"
            >
              <Skeleton className="size-2.5 rounded-full shrink-0" />
              <Skeleton className="h-3.5 w-20 shrink-0" />
              <Skeleton className="h-3.5 w-28 shrink-0" />
              <Skeleton className="h-3.5 flex-1" />
              <Skeleton className="h-5 w-24 rounded-full shrink-0" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState title="Không tải được danh sách y lệnh" message={error} onRetry={onRetry} />
      ) : totalCount === 0 ? (
        <div className="rounded-md border border-line bg-surface">
          <EmptyState
            role="status"
            icon={ClipboardList}
            title="Không có y lệnh chờ thẩm định"
          />
        </div>
      ) : orders.length === 0 ? (
        <div className="rounded-md border border-line bg-surface">
          <EmptyState
            role="status"
            icon={ClipboardList}
            title="Không có y lệnh phù hợp bộ lọc"
            description="Thử thay đổi từ khoá tìm kiếm hoặc quay về danh sách Tất cả."
            action={
              <Button variant="secondary" size="sm" onClick={onResetFilters}>
                Xoá bộ lọc
              </Button>
            }
          />
        </div>
      ) : (
        <div className="relative w-full rounded-md border border-line bg-surface">
          <table className="orders-table w-full table-fixed border-collapse text-sm" aria-label="Danh sách y lệnh">
            <colgroup>
              <col className="order-dot" /><col className="order-time" />
              <col className="order-code" /><col className="order-patient" />
              <col className="order-dept" /><col /><col className="order-result" />
              <col className="order-feedback" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-surface-muted">
              <tr className="h-9 border-b border-line text-left text-2xs font-medium uppercase tracking-[0.04em] text-fg-subtle">
                <th scope="col">
                  <span className="sr-only">Mức độ</span>
                </th>
                <th scope="col" aria-sort={sortField === 'thoi_diem_ke' ? sortDirection === 'asc' ? 'ascending' : 'descending' : 'none'}>
                  <button type="button" onClick={() => onToggleSort('thoi_diem_ke')} className="inline-flex min-h-7 cursor-pointer items-center gap-0.5 text-left">
                    Thời điểm kê
                    {sortField === 'thoi_diem_ke' ? sortDirection === 'asc' ? <ArrowUp className="size-3 shrink-0" /> : <ArrowDown className="size-3 shrink-0" /> : <ArrowUpDown className="size-3 shrink-0" />}
                  </button>
                </th>
                <th scope="col">Mã y lệnh</th>
                <th scope="col">Người bệnh</th>
                <th scope="col">Khoa</th>
                <th scope="col">Thuốc</th>
                <th
                  scope="col"
                  aria-sort={
                    isResultSorted
                      ? sortDirection === 'desc'
                        ? 'descending'
                        : 'ascending'
                      : 'none'
                  }
                >
                  <button
                    type="button"
                    onClick={() => onToggleSort('ket_qua')}
                    className="inline-flex cursor-pointer items-center gap-1 uppercase tracking-[0.04em] text-fg-subtle hover:text-fg"
                  >
                    <span>Kết quả</span>
                    <SortIcon className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                  </button>
                </th>
                <th scope="col" className="text-center" title="Phản hồi">
                  <CheckCheck className="size-3.5" aria-hidden="true" /><span className="sr-only">Phản hồi</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {orders.map((item) => (
                <tr
                  key={item.ca_id}
                  title={item.mo_ta}
                  ref={(el) => {
                    rowRefs.current[item.ca_id] = el
                  }}
                  tabIndex={0}
                  onClick={() => onOpenOrder(item.ca_id)}
                  onKeyDown={(e) => handleRowKeyDown(e, item.ca_id)}
                  className="h-[44px] cursor-pointer transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-primary-soft/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                >
                  <td>
                    <span
                      className={cn(
                        'inline-block size-2.5 rounded-full align-middle',
                        PRIORITY_DOT_CLASS[item.uu_tien],
                      )}
                      aria-hidden="true"
                    />
                    <span className="sr-only">{PRIORITY_SR_LABEL[item.uu_tien]}</span>
                  </td>
                  <td className="font-mono text-xs tabular-nums">
                    {item.thoi_diem_ke ? <time dateTime={item.thoi_diem_ke} title={formatReadableDateTime(item.thoi_diem_ke)}>{formatReadableDateTime(item.thoi_diem_ke).replace(/\/\d{4}$/, '').split(' · ').map((part, index) => <span key={index} className="block">{part}</span>)}</time> : null}
                  </td>
                  <td className="font-mono text-xs font-medium text-fg" title={item.ma_y_lenh ?? undefined}>
                    <span className="block truncate">{item.ma_y_lenh ?? ''}</span>
                  </td>
                  <td className="text-xs text-fg-muted">{item.nguoi_benh_tom_tat ?? ''}</td>
                  <td className="text-sm text-fg-muted" title={item.khoa}><span className="block truncate">{item.khoa}</span></td>
                  <td title={item.thuoc?.join(', ')}>
                    <div className="flex min-w-0 items-center gap-1">
                      <span className="min-w-0 truncate">{item.thuoc?.[0] ?? ''}</span>
                      {item.thuoc && item.thuoc.length > 1 ? <span className="shrink-0 text-xs text-fg-subtle">+{item.thuoc.length - 1}</span> : null}
                    </div>
                  </td>
                  <td title={item.huy_hieu}>
                    <ResultBadges item={item} />
                  </td>
                  <td className="text-center">
                    {item.da_phan_hoi_het ? (
                      <span
                        className="inline-flex items-center justify-end gap-1 text-xs font-medium text-success-fg"
                        title="Đã phản hồi hết"
                      >
                        <CheckCheck className="size-4" strokeWidth={1.75} aria-hidden="true" />
                        <span className="sr-only">Đã phản hồi</span>
                      </span>
                    ) : (
                      <span className="sr-only">Chưa phản hồi hết</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
