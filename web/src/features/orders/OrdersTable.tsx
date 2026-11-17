import {
  Calendar,
  Check,
  ChevronDown,
  CircleCheck,
  CircleHelp,
  ClipboardList,
  FileQuestion,
  OctagonAlert,
  TriangleAlert,
  X,
} from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { DongHangDoi, LoiNapCa } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { InlineAlert } from '@/components/ui/inline-alert'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ErrorState } from '@/features/states/StateViews'
import { cn } from '@/lib/cn'
import { formatReadableDateTime } from '@/lib/displayFormat'
import {
  ORDER_AI_WARNING_LABELS,
  ORDER_PRIORITY_LABELS,
  ORDER_STATUS_LABELS,
  applyOrderColumnFilters,
  getOrderAiWarningKind,
  getOrderAiWarningTooltip,
  getOrderPatientCode,
  getOrderPriorityLevel,
  getOrderWorkflowStatus,
  stepOrderSelection,
} from '@/lib/orders'
import type {
  OrderAiWarningFilter,
  OrderColumnFilters,
  OrderPriorityLevel,
  OrderRowInput,
  OrderSortDirection,
  OrderSortField,
  OrderWorkflowStatus,
} from '@/lib/orders'

export interface OrdersTableProps {
  filterTitle: string
  orders: readonly OrderRowInput[]
  totalCount: number
  loiNap: readonly LoiNapCa[]
  loading: boolean
  error: string | null
  searchQuery: string
  sortField: OrderSortField
  sortDirection: OrderSortDirection
  departments?: readonly string[]
  onToggleSort: (field: OrderSortField) => void
  onSelectSort?: (field: OrderSortField, direction: OrderSortDirection) => void
  onOpenOrder: (caId: string) => void
  onResetFilters: () => void
  onRetry: () => void
}

const PRIORITY_DOT_CLASS: Record<OrderPriorityLevel, string> = {
  cao: 'bg-danger-solid',
  trung_binh: 'bg-warning-solid',
  thap: 'bg-success-solid',
}

const STATUS_BADGE_TONE: Record<
  OrderWorkflowStatus,
  'success' | 'warning' | 'missing' | 'neutral'
> = {
  da_duyet: 'success',
  chua_duyet: 'warning',
  dang_cho: 'missing',
  da_huy: 'neutral',
}

const STATUS_SHORT_LABELS: Record<OrderWorkflowStatus, string> = {
  chua_duyet: 'Chưa duyệt',
  da_duyet: 'Đã duyệt',
  dang_cho: 'Đang chờ',
  da_huy: 'Đã hủy',
}

const AI_WARNING_ICON_STYLE: Record<
  OrderAiWarningFilter,
  {
    icon: typeof OctagonAlert
    className: string
    label: string
  }
> = {
  nghiem_trong: {
    icon: OctagonAlert,
    className: 'border-danger-line bg-danger-bg text-danger-fg',
    label: 'Nghiêm trọng',
  },
  can_luu_y: {
    icon: TriangleAlert,
    className: 'border-warning-line bg-warning-bg text-warning-fg',
    label: 'Cần lưu ý',
  },
  thieu_du_lieu: {
    icon: CircleHelp,
    className: 'border-missing-line bg-missing-bg text-missing-fg',
    label: 'Thiếu dữ liệu',
  },
  ngoai_hdsd: {
    icon: FileQuestion,
    className: 'border-offlabel-line bg-offlabel-bg text-offlabel-fg',
    label: 'Ngoài HDSD',
  },
  dat: {
    icon: CircleCheck,
    className: 'border-success-line bg-success-bg text-success-fg',
    label: 'Đạt',
  },
}

function AiWarningIconCell({ item }: { item: DongHangDoi }) {
  const kind = getOrderAiWarningKind(item)
  const spec = AI_WARNING_ICON_STYLE[kind]
  const Icon = spec.icon
  const tooltipText = getOrderAiWarningTooltip(item)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          role="img"
          aria-label={tooltipText}
          title={tooltipText}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            'inline-flex size-6 items-center justify-center rounded-full border transition-transform duration-120 hover:scale-105',
            spec.className,
          )}
        >
          <Icon className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        </span>
      </TooltipTrigger>
      <TooltipContent side="left" className="max-w-xs text-xs leading-relaxed">
        {tooltipText}
      </TooltipContent>
    </Tooltip>
  )
}

function SortMenuItems({
  field,
  aliasField,
  sortField,
  sortDirection,
  ascLabel,
  descLabel,
  onApplySort,
}: {
  field: OrderSortField
  aliasField?: OrderSortField
  sortField: OrderSortField
  sortDirection: OrderSortDirection
  ascLabel: string
  descLabel: string
  onApplySort: (field: OrderSortField, direction: OrderSortDirection) => void
}) {
  const isFieldActive =
    sortField === field || (aliasField !== undefined && sortField === aliasField)

  return (
    <>
      <div className="px-2 py-1 font-semibold text-fg-subtle">Sắp xếp</div>
      <PopoverClose asChild>
        <button
          type="button"
          onClick={() => onApplySort(field, 'asc')}
          className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
        >
          <span>{ascLabel}</span>
          {isFieldActive && sortDirection === 'asc' ? (
            <Check className="size-3.5 text-primary" />
          ) : null}
        </button>
      </PopoverClose>
      <PopoverClose asChild>
        <button
          type="button"
          onClick={() => onApplySort(field, 'desc')}
          className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
        >
          <span>{descLabel}</span>
          {isFieldActive && sortDirection === 'desc' ? (
            <Check className="size-3.5 text-primary" />
          ) : null}
        </button>
      </PopoverClose>
    </>
  )
}

/** Danh sách y lệnh 8 cột gọn phẳng: mỗi cột chỉ có 1 mũi tên hướng xuống mở menu sắp xếp & lọc. */
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
  departments,
  onToggleSort,
  onSelectSort,
  onOpenOrder,
  onResetFilters,
  onRetry,
}: OrdersTableProps) {
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({})
  const dateInputRef = useRef<HTMLInputElement | null>(null)
  const [columnFilters, setColumnFilters] = useState<OrderColumnFilters>({
    priority: 'all',
    khoa: 'all',
    status: 'all',
    aiWarning: 'all',
    timeText: '',
    dateExact: '',
  })

  const handleApplySort = (field: OrderSortField, direction: OrderSortDirection) => {
    if (onSelectSort) {
      onSelectSort(field, direction)
      return
    }
    onToggleSort(field)
  }

  const availableDepartments = useMemo(() => {
    if (departments && departments.length > 0) {
      return [...departments]
    }
    const set = new Set<string>()
    for (const item of orders) {
      if (item.khoa) {
        set.add(item.khoa)
      }
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'vi'))
  }, [departments, orders])

  const displayedOrders = useMemo(
    () => applyOrderColumnFilters(orders, columnFilters),
    [orders, columnFilters],
  )

  const hasActiveColumnFilter = Boolean(
    (columnFilters.priority && columnFilters.priority !== 'all') ||
      (columnFilters.khoa && columnFilters.khoa !== 'all') ||
      (columnFilters.status && columnFilters.status !== 'all') ||
      (columnFilters.aiWarning && columnFilters.aiWarning !== 'all') ||
      columnFilters.timeText?.trim() ||
      columnFilters.dateExact?.trim(),
  )

  const handleClearAllFilters = () => {
    setColumnFilters({
      priority: 'all',
      khoa: 'all',
      status: 'all',
      aiWarning: 'all',
      timeText: '',
      dateExact: '',
    })
    onResetFilters()
  }

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
    const nextId = stepOrderSelection(displayedOrders, caId, direction)
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

  const getAriaSort = (
    field: OrderSortField,
    aliasField?: OrderSortField,
  ): 'ascending' | 'descending' | undefined => {
    const isSorted = sortField === field || (aliasField !== undefined && sortField === aliasField)
    if (!isSorted) {
      return undefined
    }
    return sortDirection === 'asc' ? 'ascending' : 'descending'
  }

  return (
    <div className="orders-panel flex min-w-0 flex-col gap-3">
      {/* Đầu trang danh sách: đồng bộ font chữ hệ thống Plus Jakarta Sans */}
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-2.5">
          <h1 className="text-lg font-semibold tracking-tight text-fg">
            {filterTitle}
          </h1>
          <span className="font-mono text-xs text-fg-subtle tabular-nums">
            {loading ? 'Đang tải…' : `${displayedOrders.length} y lệnh`}
          </span>
          {searchQuery.trim() ? (
            <span className="text-xs text-fg-muted">
              · Tìm &ldquo;{searchQuery.trim()}&rdquo;
            </span>
          ) : null}
        </div>

        {(searchQuery.trim() || hasActiveColumnFilter || displayedOrders.length !== totalCount) &&
        !loading ? (
          <Button variant="ghost" size="sm" onClick={handleClearAllFilters}>
            Xoá bộ lọc ({totalCount})
          </Button>
        ) : null}
      </div>

      {/* Dải chip hiển thị nhanh các bộ lọc cột đang bật */}
      {hasActiveColumnFilter ? (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-fg-subtle">Đang lọc:</span>
          {columnFilters.priority && columnFilters.priority !== 'all' ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Ưu tiên: {ORDER_PRIORITY_LABELS[columnFilters.priority]}</span>
              <button
                type="button"
                aria-label="Bỏ lọc ưu tiên"
                onClick={() => setColumnFilters((prev) => ({ ...prev, priority: 'all' }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {columnFilters.khoa && columnFilters.khoa !== 'all' ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Khoa: {columnFilters.khoa}</span>
              <button
                type="button"
                aria-label="Bỏ lọc khoa"
                onClick={() => setColumnFilters((prev) => ({ ...prev, khoa: 'all' }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {columnFilters.status && columnFilters.status !== 'all' ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Trạng thái: {ORDER_STATUS_LABELS[columnFilters.status]}</span>
              <button
                type="button"
                aria-label="Bỏ lọc trạng thái"
                onClick={() => setColumnFilters((prev) => ({ ...prev, status: 'all' }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {columnFilters.aiWarning && columnFilters.aiWarning !== 'all' ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Cảnh báo: {ORDER_AI_WARNING_LABELS[columnFilters.aiWarning]}</span>
              <button
                type="button"
                aria-label="Bỏ lọc cảnh báo AI"
                onClick={() => setColumnFilters((prev) => ({ ...prev, aiWarning: 'all' }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {columnFilters.dateExact ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Ngày: {columnFilters.dateExact}</span>
              <button
                type="button"
                aria-label="Bỏ lọc ngày kê"
                onClick={() => setColumnFilters((prev) => ({ ...prev, dateExact: '' }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {columnFilters.timeText?.trim() ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Thời điểm: {columnFilters.timeText.trim()}</span>
              <button
                type="button"
                aria-label="Bỏ lọc chuỗi thời điểm"
                onClick={() => setColumnFilters((prev) => ({ ...prev, timeText: '' }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
        </div>
      ) : null}

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
      ) : (
        <div
          role="region"
          aria-label="Bảng danh sách y lệnh"
          tabIndex={0}
          className="relative w-full overflow-x-auto rounded-md border border-line bg-surface"
        >
          <table
            className="orders-table w-full table-fixed border-collapse text-xs"
            aria-label="Danh sách y lệnh"
          >
            <colgroup>
              <col className="order-priority" />
              <col className="order-time" />
              <col className="order-code" />
              <col className="order-patient-id" />
              <col className="order-patient" />
              <col className="order-dept" />
              <col className="order-status" />
              <col className="order-ai-warn" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-surface-muted">
              <tr className="h-9 border-b border-line text-left text-xs font-medium text-fg-subtle">
                {/* 1. Ưu tiên */}
                <th scope="col" aria-sort={getAriaSort('uu_tien', 'ket_qua')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          (columnFilters.priority !== 'all' ||
                            sortField === 'uu_tien' ||
                            sortField === 'ket_qua') &&
                            'text-fg',
                        )}
                      >
                        <span>Ưu tiên</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-48 p-1.5 text-xs">
                      <SortMenuItems
                        field="uu_tien"
                        aliasField="ket_qua"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        descLabel="Cao → Thấp"
                        ascLabel="Thấp → Cao"
                        onApplySort={handleApplySort}
                      />
                      <hr className="my-1 border-line" />
                      <div className="px-2 py-1 font-semibold text-fg-subtle">Lọc mức ưu tiên</div>
                      {(['all', 'cao', 'trung_binh', 'thap'] as const).map((level) => {
                        const selected = (columnFilters.priority ?? 'all') === level
                        return (
                          <PopoverClose key={level} asChild>
                            <button
                              type="button"
                              onClick={() =>
                                setColumnFilters((prev) => ({ ...prev, priority: level }))
                              }
                              className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
                            >
                              <span>
                                {level === 'all' ? 'Tất cả mức độ' : ORDER_PRIORITY_LABELS[level]}
                              </span>
                              {selected ? <Check className="size-3.5 text-primary" /> : null}
                            </button>
                          </PopoverClose>
                        )
                      })}
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 2. Thời điểm kê */}
                <th scope="col" aria-sort={getAriaSort('thoi_diem_ke')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          (columnFilters.dateExact ||
                            columnFilters.timeText?.trim() ||
                            sortField === 'thoi_diem_ke') &&
                            'text-fg',
                        )}
                      >
                        <span>Thời điểm kê</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-64 p-2 text-xs">
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-col">
                          <SortMenuItems
                            field="thoi_diem_ke"
                            sortField={sortField}
                            sortDirection={sortDirection}
                            descLabel="Mới nhất trước"
                            ascLabel="Cũ nhất trước"
                            onApplySort={handleApplySort}
                          />
                        </div>

                        <hr className="border-line" />

                        <div className="flex flex-col gap-1 px-1">
                          <label
                            htmlFor="order-time-text-filter"
                            className="font-medium text-fg-muted"
                          >
                            Tự nhập giờ hoặc ngày
                          </label>
                          <input
                            id="order-time-text-filter"
                            type="text"
                            value={columnFilters.timeText ?? ''}
                            onChange={(e) =>
                              setColumnFilters((prev) => ({ ...prev, timeText: e.target.value }))
                            }
                            placeholder="VD: 07:55 hoặc 10/11/2026"
                            className="h-7 w-full rounded-sm border border-line-strong bg-surface px-2 font-mono text-xs text-fg placeholder:font-sans placeholder:text-fg-subtle focus:border-primary"
                          />
                        </div>

                        <div className="flex flex-col gap-1 px-1">
                          <div className="flex items-center justify-between">
                            <label
                              htmlFor="order-date-picker-filter"
                              className="font-medium text-fg-muted"
                            >
                              Chọn ngày từ lịch
                            </label>
                            <button
                              type="button"
                              onClick={() => {
                                const inputEl = dateInputRef.current
                                if (!inputEl) return
                                if (typeof inputEl.showPicker === 'function') {
                                  inputEl.showPicker()
                                } else {
                                  inputEl.focus()
                                }
                              }}
                              className="inline-flex cursor-pointer items-center gap-1 text-2xs font-medium text-primary hover:underline"
                            >
                              <Calendar className="size-3" aria-hidden="true" />
                              <span>Mở lịch</span>
                            </button>
                          </div>
                          <input
                            ref={dateInputRef}
                            id="order-date-picker-filter"
                            type="date"
                            value={columnFilters.dateExact ?? ''}
                            onChange={(e) =>
                              setColumnFilters((prev) => ({ ...prev, dateExact: e.target.value }))
                            }
                            className="h-7 w-full cursor-pointer rounded-sm border border-line-strong bg-surface px-2 font-mono text-xs text-fg focus:border-primary"
                          />
                        </div>

                        {columnFilters.timeText?.trim() || columnFilters.dateExact ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setColumnFilters((prev) => ({
                                ...prev,
                                timeText: '',
                                dateExact: '',
                              }))
                            }
                            className="w-full justify-center"
                          >
                            Xoá lọc thời điểm
                          </Button>
                        ) : null}
                      </div>
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 3. Mã y lệnh */}
                <th scope="col" aria-sort={getAriaSort('ma_y_lenh')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          sortField === 'ma_y_lenh' && 'text-fg',
                        )}
                      >
                        <span>Mã y lệnh</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-44 p-1.5 text-xs">
                      <SortMenuItems
                        field="ma_y_lenh"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        ascLabel="Mã A → Z"
                        descLabel="Mã Z → A"
                        onApplySort={handleApplySort}
                      />
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 4. Mã BN */}
                <th scope="col" aria-sort={getAriaSort('ma_bn')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          sortField === 'ma_bn' && 'text-fg',
                        )}
                      >
                        <span>Mã BN</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-44 p-1.5 text-xs">
                      <SortMenuItems
                        field="ma_bn"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        ascLabel="Mã BN A → Z"
                        descLabel="Mã BN Z → A"
                        onApplySort={handleApplySort}
                      />
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 5. Người bệnh */}
                <th scope="col" aria-sort={getAriaSort('nguoi_benh')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          sortField === 'nguoi_benh' && 'text-fg',
                        )}
                      >
                        <span>Người bệnh</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-48 p-1.5 text-xs">
                      <SortMenuItems
                        field="nguoi_benh"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        ascLabel="Tăng dần (A → Z)"
                        descLabel="Giảm dần (Z → A)"
                        onApplySort={handleApplySort}
                      />
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 6. Khoa */}
                <th scope="col" aria-sort={getAriaSort('khoa')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          (columnFilters.khoa !== 'all' || sortField === 'khoa') && 'text-fg',
                        )}
                      >
                        <span>Khoa</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-56 p-1.5 text-xs">
                      <SortMenuItems
                        field="khoa"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        ascLabel="Khoa A → Z"
                        descLabel="Khoa Z → A"
                        onApplySort={handleApplySort}
                      />
                      <hr className="my-1 border-line" />
                      <div className="px-2 py-1 font-semibold text-fg-subtle">Chọn khoa</div>
                      <PopoverClose asChild>
                        <button
                          type="button"
                          onClick={() => setColumnFilters((prev) => ({ ...prev, khoa: 'all' }))}
                          className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
                        >
                          <span>Tất cả khoa</span>
                          {(columnFilters.khoa ?? 'all') === 'all' ? (
                            <Check className="size-3.5 text-primary" />
                          ) : null}
                        </button>
                      </PopoverClose>
                      {availableDepartments.map((dept) => {
                        const selected = columnFilters.khoa === dept
                        return (
                          <PopoverClose key={dept} asChild>
                            <button
                              type="button"
                              onClick={() =>
                                setColumnFilters((prev) => ({ ...prev, khoa: dept }))
                              }
                              className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
                            >
                              <span className="truncate">{dept}</span>
                              {selected ? <Check className="size-3.5 shrink-0 text-primary" /> : null}
                            </button>
                          </PopoverClose>
                        )
                      })}
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 7. Trạng thái */}
                <th scope="col" aria-sort={getAriaSort('trang_thai')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          (columnFilters.status !== 'all' || sortField === 'trang_thai') &&
                            'text-fg',
                        )}
                      >
                        <span>Trạng thái</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="end" className="w-56 p-1.5 text-xs">
                      <SortMenuItems
                        field="trang_thai"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        ascLabel="Chưa duyệt → Đã duyệt"
                        descLabel="Đã duyệt → Chưa duyệt"
                        onApplySort={handleApplySort}
                      />
                      <hr className="my-1 border-line" />
                      <div className="px-2 py-1 font-semibold text-fg-subtle">Lọc trạng thái</div>
                      {(
                        ['all', 'chua_duyet', 'da_duyet', 'dang_cho', 'da_huy'] as const
                      ).map((st) => {
                        const selected = (columnFilters.status ?? 'all') === st
                        return (
                          <PopoverClose key={st} asChild>
                            <button
                              type="button"
                              onClick={() =>
                                setColumnFilters((prev) => ({ ...prev, status: st }))
                              }
                              className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
                            >
                              <span>
                                {st === 'all' ? 'Tất cả trạng thái' : ORDER_STATUS_LABELS[st]}
                              </span>
                              {selected ? <Check className="size-3.5 text-primary" /> : null}
                            </button>
                          </PopoverClose>
                        )
                      })}
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 8. Cảnh báo AI */}
                <th scope="col" aria-sort={getAriaSort('ket_qua')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center justify-center gap-1 rounded-sm px-1 text-center font-medium transition-colors hover:text-fg',
                          (columnFilters.aiWarning !== 'all' || sortField === 'ket_qua') &&
                            'text-fg',
                        )}
                      >
                        <span>Cảnh báo AI</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="end" className="w-52 p-1.5 text-xs">
                      <SortMenuItems
                        field="ket_qua"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        descLabel="Nghiêm trọng trước"
                        ascLabel="Đạt trước"
                        onApplySort={handleApplySort}
                      />
                      <hr className="my-1 border-line" />
                      <div className="px-2 py-1 font-semibold text-fg-subtle">Lọc cảnh báo AI</div>
                      {(
                        [
                          'all',
                          'nghiem_trong',
                          'can_luu_y',
                          'thieu_du_lieu',
                          'ngoai_hdsd',
                          'dat',
                        ] as const
                      ).map((warn) => {
                        const selected = (columnFilters.aiWarning ?? 'all') === warn
                        return (
                          <PopoverClose key={warn} asChild>
                            <button
                              type="button"
                              onClick={() =>
                                setColumnFilters((prev) => ({ ...prev, aiWarning: warn }))
                              }
                              className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
                            >
                              <span>
                                {warn === 'all'
                                  ? 'Tất cả cảnh báo'
                                  : ORDER_AI_WARNING_LABELS[warn]}
                              </span>
                              {selected ? <Check className="size-3.5 text-primary" /> : null}
                            </button>
                          </PopoverClose>
                        )
                      })}
                    </PopoverContent>
                  </Popover>
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-line bg-surface">
              {displayedOrders.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <p className="text-sm font-medium text-fg">
                        Không có y lệnh phù hợp bộ lọc hiện tại
                      </p>
                      <Button variant="secondary" size="sm" onClick={handleClearAllFilters}>
                        Xoá bộ lọc
                      </Button>
                    </div>
                  </td>
                </tr>
              ) : (
                displayedOrders.map((item) => {
                  const priorityLevel = getOrderPriorityLevel(item)
                  const priorityLabel = ORDER_PRIORITY_LABELS[priorityLevel]
                  const patientCode = getOrderPatientCode(item)
                  const workflowStatus = getOrderWorkflowStatus(item)
                  const statusShortLabel = STATUS_SHORT_LABELS[workflowStatus]
                  const statusFullLabel = ORDER_STATUS_LABELS[workflowStatus]

                  return (
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
                      {/* 1. Ưu tiên */}
                      <td className="whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-fg">
                          <span
                            className={cn(
                              'inline-block size-2 rounded-full shrink-0',
                              PRIORITY_DOT_CLASS[priorityLevel],
                            )}
                            aria-hidden="true"
                          />
                          <span className="truncate">{priorityLabel}</span>
                        </span>
                      </td>

                      {/* 2. Thời điểm kê */}
                      <td className="font-mono text-xs tabular-nums whitespace-nowrap text-fg-muted">
                        {item.thoi_diem_ke ? (
                          <time
                            dateTime={item.thoi_diem_ke}
                            title={formatReadableDateTime(item.thoi_diem_ke)}
                          >
                            {formatReadableDateTime(item.thoi_diem_ke)
                              .replace(/\/\d{4}$/, '')
                              .split(' · ')
                              .map((part, index) => (
                                <span key={index} className="block leading-tight">
                                  {part}
                                </span>
                              ))}
                          </time>
                        ) : null}
                      </td>

                      {/* 3. Mã y lệnh */}
                      <td
                        className="font-mono text-xs font-semibold text-fg whitespace-nowrap"
                        title={item.ma_y_lenh ?? undefined}
                      >
                        <span className="block truncate">{item.ma_y_lenh ?? ''}</span>
                      </td>

                      {/* 4. Mã BN */}
                      <td
                        className="font-mono text-xs text-fg-muted whitespace-nowrap"
                        title={patientCode || undefined}
                      >
                        <span className="block truncate">{patientCode}</span>
                      </td>

                      {/* 5. Người bệnh */}
                      <td
                        className="text-xs text-fg whitespace-nowrap"
                        title={item.nguoi_benh_tom_tat ?? undefined}
                      >
                        <span className="block truncate">{item.nguoi_benh_tom_tat ?? ''}</span>
                      </td>

                      {/* 6. Khoa */}
                      <td className="text-xs text-fg-muted whitespace-nowrap" title={item.khoa}>
                        <span className="block truncate">{item.khoa}</span>
                      </td>

                      {/* 7. Trạng thái */}
                      <td className="whitespace-nowrap" title={statusFullLabel}>
                        <Badge tone={STATUS_BADGE_TONE[workflowStatus]} variant="soft">
                          {statusShortLabel}
                        </Badge>
                      </td>

                      {/* 8. Cảnh báo AI (chỉ icon + tooltip khi hover) */}
                      <td className="text-center">
                        <AiWarningIconCell item={item} />
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
