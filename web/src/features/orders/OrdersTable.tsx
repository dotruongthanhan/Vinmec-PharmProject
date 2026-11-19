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
import { useMemo, useRef } from 'react'
import type { Dispatch, KeyboardEvent, SetStateAction } from 'react'
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
import { formatReadableDateTime, VIETNAM_TIME_ZONE } from '@/lib/displayFormat'
import {
  ORDER_AI_WARNING_LABELS,
  ORDER_PRIORITY_LABELS,
  ORDER_STATUS_LABELS,
  applyOrderColumnFilters,
  formatDiagnosesWithIcd,
  getLatestPendingTime,
  getOldestPendingTime,
  getOrderAiWarningKind,
  getOrderAiWarningTooltip,
  getOrderPatientCode,
  getOrderPriorityLevel,
  getOrderWorkflowStatus,
  getPendingOrderCount,
  selectedFilterValues,
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
  columnFilters: OrderColumnFilters
  onColumnFiltersChange: Dispatch<SetStateAction<OrderColumnFilters>>
  departments?: readonly string[]
  updatedAt?: Date | null
  onToggleSort: (field: OrderSortField) => void
  onSelectSort?: (field: OrderSortField, direction: OrderSortDirection) => void
  onOpenOrder: (caId: string) => void
  onResetFilters: () => void
  onRetry: () => void
  onRefresh: () => void
}

const UPDATE_TIME = new Intl.DateTimeFormat('vi-VN', {
  timeZone: VIETNAM_TIME_ZONE, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
})
const PRIORITY_OPTIONS = Object.keys(ORDER_PRIORITY_LABELS) as OrderPriorityLevel[]
const STATUS_OPTIONS = Object.keys(ORDER_STATUS_LABELS) as OrderWorkflowStatus[]
const WARNING_OPTIONS = Object.keys(ORDER_AI_WARNING_LABELS) as OrderAiWarningFilter[]

const PRIORITY_DOT_CLASS: Record<OrderPriorityLevel, string> = {
  cao: 'bg-danger-solid',
  trung_binh: 'bg-warning-solid',
  thap: 'bg-success-solid',
}

const STATUS_BADGE_TONE: Record<
  OrderWorkflowStatus,
  'success' | 'warning' | 'missing' | 'neutral'
> = {
  chua_duyet: 'warning',
  dang_cho: 'missing',
  da_huy: 'neutral',
  da_xong: 'success',
}

const STATUS_SHORT_LABELS: Record<OrderWorkflowStatus, string> = {
  chua_duyet: 'Chưa duyệt',
  dang_cho: 'Đang chờ',
  da_huy: 'Đã hủy',
  da_xong: 'Đã xong',
}

function FormattedTimestampCell({ value }: { value: string | null }) {
  if (!value) {
    return <span className="text-fg-subtle">—</span>
  }
  const readable = formatReadableDateTime(value)
  return (
    <time dateTime={value} title={readable}>
      {readable
        .replace(/\/\d{4}$/, '')
        .split(' · ')
        .map((part, index) => (
          <span key={index} className="block leading-tight">
            {part}
          </span>
        ))}
    </time>
  )
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
          aria-pressed={isFieldActive && sortDirection === 'asc'}
          onClick={() => onApplySort(field, 'asc')}
          className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
        >
          <span>{ascLabel}</span>
          {isFieldActive && sortDirection === 'asc' ? (
            <Check className="size-3.5 text-primary" aria-hidden="true" />
          ) : null}
        </button>
      </PopoverClose>
      <PopoverClose asChild>
        <button
          type="button"
          aria-pressed={isFieldActive && sortDirection === 'desc'}
          onClick={() => onApplySort(field, 'desc')}
          className="flex w-full cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-left text-fg hover:bg-surface-hover"
        >
          <span>{descLabel}</span>
          {isFieldActive && sortDirection === 'desc' ? (
            <Check className="size-3.5 text-primary" aria-hidden="true" />
          ) : null}
        </button>
      </PopoverClose>
    </>
  )
}

function FilterCheckbox({ checked, children, onCheck }: {
  checked: boolean; children: string; onCheck: (checked: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-fg hover:bg-surface-hover">
      <input type="checkbox" checked={checked}
        className="size-3.5 shrink-0 cursor-pointer accent-primary"
        onChange={(event) => onCheck(event.currentTarget.checked)} />
      <span>{children}</span>
    </label>
  )
}

function ColumnFilterMenu<T extends string>({
  label,
  options,
  selected,
  onChange,
  optionLabel = (value: T) => value,
  align = 'start',
  ...sortProps
}: Parameters<typeof SortMenuItems>[0] & {
  label: string
  options: readonly T[]
  selected: readonly T[]
  onChange: (values: T[]) => void
  optionLabel?: (value: T) => string
  align?: 'start' | 'end'
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className={cn(
          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
          (selected.length > 0 || sortProps.sortField === sortProps.field || sortProps.sortField === sortProps.aliasField) && 'text-fg',
        )}>
          <span>{label}</span>
          {selected.length > 0 ? (
            <span className="rounded-full bg-primary-soft px-1.5 text-primary tabular-nums">
              {selected.length}<span className="sr-only"> lựa chọn đang lọc</span>
            </span>
          ) : null}
          <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent align={align} aria-label={label} className="w-56 p-1.5 text-xs">
        <SortMenuItems {...sortProps} />
        <fieldset className="mt-1 min-w-0 border-t border-line">
          <legend className="px-2 py-1 font-semibold text-fg-subtle">Lọc</legend>
          <div className="max-h-52 overflow-y-auto">
            <FilterCheckbox checked={selected.length === 0} onCheck={() => onChange([])}>Tất cả</FilterCheckbox>
            {options.map((value) => (
              <FilterCheckbox key={value} checked={selected.includes(value)}
                onCheck={(checked) => onChange(checked ? [...selected, value] : selected.filter((entry) => entry !== value))}>
                {optionLabel(value)}
              </FilterCheckbox>
            ))}
          </div>
        </fieldset>
      </PopoverContent>
    </Popover>
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
  columnFilters,
  onColumnFiltersChange: setColumnFilters,
  departments,
  updatedAt,
  onToggleSort,
  onSelectSort,
  onOpenOrder,
  onResetFilters,
  onRetry,
  onRefresh,
}: OrdersTableProps) {
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({})
  const dateInputRef = useRef<HTMLInputElement | null>(null)
  const priorities = selectedFilterValues(columnFilters.priority)
  const selectedDepartments = selectedFilterValues(columnFilters.khoa)
  const statuses = selectedFilterValues(columnFilters.status)
  const warnings = selectedFilterValues(columnFilters.aiWarning)

  const handleApplySort = (field: OrderSortField, direction: OrderSortDirection) => {
    if (onSelectSort) {
      onSelectSort(field, direction)
      return
    }
    onToggleSort(field)
  }

  const availableDepartments = useMemo(() => {
    const set = new Set(departments ?? orders.map((item) => item.khoa).filter(Boolean))
    for (const khoa of selectedFilterValues(columnFilters.khoa)) set.add(khoa)
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'vi'))
  }, [departments, orders, columnFilters.khoa])

  const displayedOrders = useMemo(
    () => applyOrderColumnFilters(orders, columnFilters),
    [orders, columnFilters],
  )

  const hasActiveColumnFilter = Boolean(
    priorities.length || selectedDepartments.length || statuses.length || warnings.length ||
      columnFilters.timeText?.trim() ||
      columnFilters.dateExact?.trim(),
  )

  const clearAllFilters = () => {
    setColumnFilters({})
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
            {loading ? 'Đang tải…' : `${displayedOrders.length} người bệnh`}
          </span>
          {searchQuery.trim() ? (
            <span className="text-xs text-fg-muted">
              · Tìm &ldquo;{searchQuery.trim()}&rdquo;
            </span>
          ) : null}
        </div>

        {(searchQuery.trim() || hasActiveColumnFilter || displayedOrders.length !== totalCount) &&
        !loading ? (
          <Button variant="ghost" size="sm" onClick={clearAllFilters}>
            Xóa tất cả bộ lọc
          </Button>
        ) : null}
      </div>

      {/* Dải chip hiển thị nhanh các bộ lọc cột đang bật */}
      {hasActiveColumnFilter ? (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-fg-subtle">Đang lọc:</span>
          {priorities.length > 0 ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Ưu tiên: {priorities.map((level) => ORDER_PRIORITY_LABELS[level]).join(', ')}</span>
              <button
                type="button"
                aria-label="Bỏ lọc ưu tiên"
                onClick={() => setColumnFilters((prev) => ({ ...prev, priority: [] }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {selectedDepartments.length > 0 ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Khoa: {selectedDepartments.join(', ')}</span>
              <button
                type="button"
                aria-label="Bỏ lọc khoa"
                onClick={() => setColumnFilters((prev) => ({ ...prev, khoa: [] }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {statuses.length > 0 ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Trạng thái: {statuses.map((status) => ORDER_STATUS_LABELS[status]).join(', ')}</span>
              <button
                type="button"
                aria-label="Bỏ lọc trạng thái"
                onClick={() => setColumnFilters((prev) => ({ ...prev, status: [] }))}
                className="cursor-pointer hover:text-fg"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ) : null}
          {warnings.length > 0 ? (
            <Badge tone="neutral" variant="soft" className="gap-1">
              <span>Cảnh báo: {warnings.map((warning) => ORDER_AI_WARNING_LABELS[warning]).join(', ')}</span>
              <button
                type="button"
                aria-label="Bỏ lọc cảnh báo AI"
                onClick={() => setColumnFilters((prev) => ({ ...prev, aiWarning: [] }))}
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
          aria-label="Đang tải danh sách người bệnh chờ duyệt"
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
        <ErrorState title="Không tải được danh sách người bệnh" message={error} onRetry={onRetry} />
      ) : totalCount === 0 ? (
        <div className="rounded-md border border-line bg-surface">
          <EmptyState
            role="status"
            icon={ClipboardList}
            title="Không có người bệnh chờ duyệt đơn"
          />
        </div>
      ) : (
        <div
          role="region"
          aria-label="Bảng danh sách người bệnh chờ duyệt đơn"
          tabIndex={0}
          className="relative w-full overflow-x-auto rounded-md border border-line bg-surface"
        >
          <table
            className="orders-table w-full min-w-[980px] table-fixed border-collapse text-xs"
            aria-label="Danh sách người bệnh chờ duyệt đơn"
          >
            <colgroup>
              <col className="order-priority" />
              <col className="order-time-oldest" />
              <col className="order-time-latest" />
              <col className="order-patient-id" />
              <col className="order-patient-name" />
              <col className="order-dept" />
              <col className="order-diagnosis" />
              <col className="order-pending-count" />
              <col className="order-status" />
              <col className="order-ai-warn" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-surface-muted">
              <tr className="h-9 border-b border-line text-left text-xs font-medium text-fg-subtle">
                {/* 1. Ưu tiên */}
                <th scope="col" aria-sort={getAriaSort('uu_tien', 'ket_qua')}>
                  <ColumnFilterMenu
                    label="Ưu tiên" field="uu_tien" aliasField="ket_qua"
                    sortField={sortField} sortDirection={sortDirection}
                    ascLabel="Thấp → Cao" descLabel="Cao → Thấp" onApplySort={handleApplySort}
                    options={PRIORITY_OPTIONS} selected={priorities}
                    optionLabel={(value) => ORDER_PRIORITY_LABELS[value]}
                    onChange={(values) => setColumnFilters((prev) => ({ ...prev, priority: values }))}
                  />
                </th>

                {/* 2. Thời điểm kê xa nhất */}
                <th scope="col" aria-sort={getAriaSort('thoi_diem_ke_xa_nhat', 'thoi_diem_ke')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          (columnFilters.dateExact ||
                            columnFilters.timeText?.trim() ||
                            sortField === 'thoi_diem_ke_xa_nhat' ||
                            sortField === 'thoi_diem_ke') &&
                            'text-fg',
                        )}
                      >
                        <span className="truncate">Kê xa nhất</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-64 p-2 text-xs">
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-col">
                          <SortMenuItems
                            field="thoi_diem_ke_xa_nhat"
                            aliasField="thoi_diem_ke"
                            sortField={sortField}
                            sortDirection={sortDirection}
                            ascLabel="Chờ lâu nhất trước"
                            descLabel="Mới hơn trước"
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

                {/* 3. Thời điểm kê gần nhất */}
                <th scope="col" aria-sort={getAriaSort('thoi_diem_ke_gan_nhat')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          sortField === 'thoi_diem_ke_gan_nhat' && 'text-fg',
                        )}
                      >
                        <span className="truncate">Kê gần nhất</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-48 p-1.5 text-xs">
                      <SortMenuItems
                        field="thoi_diem_ke_gan_nhat"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        descLabel="Mới nhất trước"
                        ascLabel="Cũ nhất trước"
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

                {/* 5. Họ tên */}
                <th scope="col" aria-sort={getAriaSort('ho_ten')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          sortField === 'ho_ten' && 'text-fg',
                        )}
                      >
                        <span>Họ tên</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-48 p-1.5 text-xs">
                      <SortMenuItems
                        field="ho_ten"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        ascLabel="Họ tên A → Z"
                        descLabel="Họ tên Z → A"
                        onApplySort={handleApplySort}
                      />
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 6. Khoa */}
                <th scope="col" aria-sort={getAriaSort('khoa')}>
                  <ColumnFilterMenu
                    label="Khoa" field="khoa"
                    sortField={sortField} sortDirection={sortDirection}
                    ascLabel="Khoa A → Z" descLabel="Khoa Z → A" onApplySort={handleApplySort}
                    options={availableDepartments} selected={selectedDepartments}
                    onChange={(values) => setColumnFilters((prev) => ({ ...prev, khoa: values }))}
                  />
                </th>

                {/* 7. Chẩn đoán (bên phải Khoa, đầy đủ tên + mã ICD-10) */}
                <th scope="col" aria-sort={getAriaSort('chan_doan')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          sortField === 'chan_doan' && 'text-fg',
                        )}
                      >
                        <span>Chẩn đoán</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-48 p-1.5 text-xs">
                      <SortMenuItems
                        field="chan_doan"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        ascLabel="Chẩn đoán A → Z"
                        descLabel="Chẩn đoán Z → A"
                        onApplySort={handleApplySort}
                      />
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 8. Số đơn chờ */}
                <th scope="col" aria-sort={getAriaSort('so_don_cho')}>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left font-medium transition-colors hover:text-fg',
                          sortField === 'so_don_cho' && 'text-fg',
                        )}
                      >
                        <span className="truncate">Đơn chờ</span>
                        <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="end" className="w-48 p-1.5 text-xs">
                      <SortMenuItems
                        field="so_don_cho"
                        sortField={sortField}
                        sortDirection={sortDirection}
                        descLabel="Nhiều đơn nhất trước"
                        ascLabel="Ít đơn nhất trước"
                        onApplySort={handleApplySort}
                      />
                    </PopoverContent>
                  </Popover>
                </th>

                {/* 9. Trạng thái NB */}
                <th scope="col" aria-sort={getAriaSort('trang_thai')}>
                  <ColumnFilterMenu
                    label="Trạng thái NB" field="trang_thai" align="end"
                    sortField={sortField} sortDirection={sortDirection}
                    ascLabel="Chưa duyệt → Đã xong" descLabel="Đã xong → Chưa duyệt" onApplySort={handleApplySort}
                    options={STATUS_OPTIONS} selected={statuses}
                    optionLabel={(value) => ORDER_STATUS_LABELS[value]}
                    onChange={(values) => setColumnFilters((prev) => ({ ...prev, status: values }))}
                  />
                </th>

                {/* 10. Cảnh báo AI */}
                <th scope="col" aria-sort={getAriaSort('ket_qua')}>
                  <ColumnFilterMenu
                    label="AI" field="ket_qua" aliasField="uu_tien" align="end"
                    sortField={sortField} sortDirection={sortDirection}
                    ascLabel="Đạt trước" descLabel="Nghiêm trọng trước" onApplySort={handleApplySort}
                    options={WARNING_OPTIONS} selected={warnings}
                    optionLabel={(value) => ORDER_AI_WARNING_LABELS[value]}
                    onChange={(values) => setColumnFilters((prev) => ({ ...prev, aiWarning: values }))}
                  />
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-line bg-surface">
              {displayedOrders.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <p className="text-sm font-medium text-fg">
                        Không có người bệnh phù hợp bộ lọc hiện tại
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                displayedOrders.map((item) => {
                  const priorityLevel = getOrderPriorityLevel(item)
                  const priorityLabel = ORDER_PRIORITY_LABELS[priorityLevel]
                  const patientCode = getOrderPatientCode(item)
                  const patientName = item.ho_ten?.trim()
                    ? item.ho_ten.trim().toLocaleUpperCase('vi-VN')
                    : 'Chưa ghi nhận'
                  const oldestTime = getOldestPendingTime(item)
                  const latestTime = getLatestPendingTime(item)
                  const diagnosisText = formatDiagnosesWithIcd(item)
                  const pendingCount = getPendingOrderCount(item)
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
                      className="min-h-[44px] cursor-pointer transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-primary-soft/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
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

                      {/* 2. Thời điểm kê xa nhất */}
                      <td className="font-mono text-xs tabular-nums whitespace-nowrap text-fg-muted">
                        <FormattedTimestampCell value={oldestTime} />
                      </td>

                      {/* 3. Thời điểm kê gần nhất */}
                      <td className="font-mono text-xs tabular-nums whitespace-nowrap text-fg-muted">
                        <FormattedTimestampCell value={latestTime} />
                      </td>

                      {/* 4. Mã BN */}
                      <td
                        className="font-mono text-xs font-semibold text-fg whitespace-nowrap"
                        title={patientCode || undefined}
                      >
                        <span className="block truncate">{patientCode || '—'}</span>
                      </td>

                      {/* 5. Họ tên */}
                      <td
                        className="text-xs font-medium text-fg whitespace-nowrap"
                        title={patientName}
                      >
                        <span className="block truncate">{patientName}</span>
                      </td>

                      {/* 6. Khoa */}
                      <td className="text-xs text-fg-muted whitespace-nowrap" title={item.khoa}>
                        <span className="block truncate">{item.khoa}</span>
                      </td>

                      {/* 7. Chẩn đoán + mã ICD-10 */}
                      <td
                        className="text-xs text-fg"
                        title={diagnosisText || undefined}
                      >
                        <span className="line-clamp-2 break-words leading-snug">
                          {diagnosisText || 'Chưa ghi nhận'}
                        </span>
                      </td>

                      {/* 8. Số đơn chờ */}
                      <td className="text-center font-mono text-xs font-semibold tabular-nums text-fg whitespace-nowrap">
                        <Badge
                          tone={pendingCount > 0 ? 'warning' : 'neutral'}
                          variant="soft"
                          className="min-w-6 justify-center font-mono tabular-nums"
                        >
                          {pendingCount}
                        </Badge>
                      </td>

                      {/* 9. Trạng thái NB */}
                      <td className="whitespace-nowrap" title={statusFullLabel}>
                        <Badge tone={STATUS_BADGE_TONE[workflowStatus]} variant="soft">
                          {statusShortLabel}
                        </Badge>
                      </td>

                      {/* 10. Cảnh báo AI (chỉ icon + tooltip khi hover) */}
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
      {updatedAt ? (
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" className="text-xs text-fg-subtle" onClick={onRefresh}>
            Cập nhật lúc <time dateTime={updatedAt.toISOString()}>{UPDATE_TIME.format(updatedAt)}</time>
          </Button>
        </div>
      ) : null}
    </div>
  )
}
