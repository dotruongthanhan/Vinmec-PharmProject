import {
  Calendar,
  Check,
  ChevronDown,
  CircleCheck,
  CircleHelp,
  FileCheck,
  FileQuestion,
  OctagonAlert,
  TriangleAlert,
  X,
} from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
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
import { administrativeDate, formatReadableDateTime, VIETNAM_TIME_ZONE } from '@/lib/displayFormat'
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
  selectedFilterValues,
  sortOrders,
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
import { DEFAULT_PAGE_SIZE, paginateItems } from '@/lib/pagination'
import { TablePagination } from './TablePagination'

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
  page?: number
  pageSize?: number
  onPageChange?: (page: number) => void
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

const HEADER_TRIGGER_CLASS =
  'inline-flex min-h-7 w-full cursor-pointer items-center gap-1 rounded-sm px-1 text-left text-2xs font-medium uppercase tracking-wide transition-colors hover:text-fg'

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
          HEADER_TRIGGER_CLASS,
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
      <PopoverContent align={align} aria-label={label} className="w-56 p-1.5 text-xs normal-case tracking-normal">
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

/** Bảng danh sách hồ sơ cần duyệt 9 cột: giữ sắp xếp, lọc từng cột, tìm kiếm và phân trang 30 dòng. */
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
  page,
  pageSize = DEFAULT_PAGE_SIZE,
  onPageChange,
  onToggleSort,
  onSelectSort,
  onOpenOrder,
  onResetFilters,
  onRetry,
  onRefresh,
}: OrdersTableProps) {
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({})
  const dateInputRef = useRef<HTMLInputElement | null>(null)
  const [internalPage, setInternalPage] = useState<number>(1)
  const isPageControlled = page !== undefined
  const activePageInput = isPageControlled ? page : internalPage

  const [prevSearchQuery, setPrevSearchQuery] = useState<string>(searchQuery)
  const [prevSortField, setPrevSortField] = useState<OrderSortField>(sortField)
  const [prevSortDirection, setPrevSortDirection] = useState<OrderSortDirection>(sortDirection)
  const [prevColumnFilters, setPrevColumnFilters] = useState<OrderColumnFilters>(columnFilters)

  if (
    prevSearchQuery !== searchQuery ||
    prevSortField !== sortField ||
    prevSortDirection !== sortDirection ||
    prevColumnFilters !== columnFilters
  ) {
    setPrevSearchQuery(searchQuery)
    setPrevSortField(sortField)
    setPrevSortDirection(sortDirection)
    setPrevColumnFilters(columnFilters)
    if (!isPageControlled && internalPage !== 1) {
      setInternalPage(1)
    }
  }

  const priorities = selectedFilterValues(columnFilters.priority)
  const selectedDepartments = selectedFilterValues(columnFilters.khoa)
  const statuses = selectedFilterValues(columnFilters.status)
  const warnings = selectedFilterValues(columnFilters.aiWarning)

  const updateColumnFilters: Dispatch<SetStateAction<OrderColumnFilters>> = (nextAction) => {
    setColumnFilters(nextAction)
    if (!isPageControlled) {
      setInternalPage(1)
    }
    onPageChange?.(1)
  }

  const handleApplySort = (field: OrderSortField, direction: OrderSortDirection) => {
    if (onSelectSort) {
      onSelectSort(field, direction)
    } else {
      onToggleSort(field)
    }
    if (!isPageControlled) {
      setInternalPage(1)
    }
    onPageChange?.(1)
  }

  const handlePageChange = (nextPage: number) => {
    if (!isPageControlled) {
      setInternalPage(nextPage)
    }
    onPageChange?.(nextPage)
  }

  const availableDepartments = useMemo(() => {
    const set = new Set(departments ?? orders.map((item) => item.khoa).filter(Boolean))
    for (const khoa of selectedFilterValues(columnFilters.khoa)) set.add(khoa)
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'vi'))
  }, [departments, orders, columnFilters.khoa])

  const displayedOrders = useMemo(() => {
    const filtered = applyOrderColumnFilters(orders, columnFilters)
    return sortOrders(filtered, sortField, sortDirection)
  }, [orders, columnFilters, sortField, sortDirection])

  const pagination = useMemo(
    () => paginateItems(displayedOrders, activePageInput, pageSize),
    [displayedOrders, activePageInput, pageSize],
  )
  const pagedOrders = pagination.items

  const hasActiveColumnFilter = Boolean(
    priorities.length || selectedDepartments.length || statuses.length || warnings.length ||
      columnFilters.timeText?.trim() ||
      columnFilters.dateExact?.trim(),
  )

  const clearAllFilters = () => {
    setColumnFilters({})
    onResetFilters()
    if (!isPageControlled) {
      setInternalPage(1)
    }
    onPageChange?.(1)
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
    const nextId = stepOrderSelection(pagedOrders, caId, direction)
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
      {/* Đầu trang danh sách */}
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-2.5">
          <h1 className="text-lg font-semibold tracking-tight text-fg">
            {filterTitle}
          </h1>
          <span className="font-mono text-xs text-fg-subtle tabular-nums">
            {loading ? 'Đang tải…' : `${displayedOrders.length} hồ sơ`}
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
                onClick={() => updateColumnFilters((prev) => ({ ...prev, priority: [] }))}
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
                onClick={() => updateColumnFilters((prev) => ({ ...prev, khoa: [] }))}
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
                onClick={() => updateColumnFilters((prev) => ({ ...prev, status: [] }))}
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
                onClick={() => updateColumnFilters((prev) => ({ ...prev, aiWarning: [] }))}
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
                onClick={() => updateColumnFilters((prev) => ({ ...prev, dateExact: '' }))}
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
                onClick={() => updateColumnFilters((prev) => ({ ...prev, timeText: '' }))}
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
          className="overflow-hidden rounded-md border border-line bg-surface shadow-xs"
          aria-busy="true"
          aria-label="Đang tải danh sách hồ sơ cần duyệt"
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
        <ErrorState title="Không tải được danh sách hồ sơ cần duyệt" message={error} onRetry={onRetry} />
      ) : totalCount === 0 ? (
        <div className="rounded-md border border-line bg-surface shadow-xs">
          <EmptyState
            role="status"
            icon={FileCheck}
            title="Không có hồ sơ cần duyệt"
          />
        </div>
      ) : (
        <>
          <div
            role="region"
            aria-label="Bảng danh sách hồ sơ cần duyệt"
            tabIndex={0}
            className="relative w-full overflow-x-auto rounded-md border border-line bg-surface shadow-xs"
          >
            <table
              className="orders-table w-full min-w-[920px] table-fixed border-collapse text-left text-sm"
              aria-label="Danh sách hồ sơ cần duyệt"
            >
              <colgroup>
                <col className="order-priority" />
                <col className="order-time" />
                <col className="order-patient-id" />
                <col className="order-patient" />
                <col className="order-dob" />
                <col className="order-dept" />
                <col className="order-diagnosis" />
                <col className="order-status" />
                <col className="order-ai-warn" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-surface-muted text-2xs font-medium uppercase tracking-wide text-fg-subtle">
                <tr className="h-9 border-b border-line">
                  {/* 1. Ưu tiên */}
                  <th scope="col" aria-sort={getAriaSort('uu_tien', 'ket_qua')}>
                    <ColumnFilterMenu
                      label="Ưu tiên" field="uu_tien" aliasField="ket_qua"
                      sortField={sortField} sortDirection={sortDirection}
                      ascLabel="Thấp → Cao" descLabel="Cao → Thấp" onApplySort={handleApplySort}
                      options={PRIORITY_OPTIONS} selected={priorities}
                      optionLabel={(value) => ORDER_PRIORITY_LABELS[value]}
                      onChange={(values) => updateColumnFilters((prev) => ({ ...prev, priority: values }))}
                    />
                  </th>

                  {/* 2. Thời điểm kê */}
                  <th scope="col" aria-sort={getAriaSort('thoi_diem_ke')}>
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className={cn(
                            HEADER_TRIGGER_CLASS,
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
                      <PopoverContent align="start" className="w-64 p-2 text-xs normal-case tracking-normal">
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
                                updateColumnFilters((prev) => ({ ...prev, timeText: e.target.value }))
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
                                updateColumnFilters((prev) => ({ ...prev, dateExact: e.target.value }))
                              }
                              className="h-7 w-full cursor-pointer rounded-sm border border-line-strong bg-surface px-2 font-mono text-xs text-fg focus:border-primary"
                            />
                          </div>

                          {columnFilters.timeText?.trim() || columnFilters.dateExact ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                updateColumnFilters((prev) => ({
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

                  {/* 3. Mã BN */}
                  <th scope="col" aria-sort={getAriaSort('ma_bn')}>
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className={cn(
                            HEADER_TRIGGER_CLASS,
                            sortField === 'ma_bn' && 'text-fg',
                          )}
                        >
                          <span>Mã BN</span>
                          <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="start" className="w-44 p-1.5 text-xs normal-case tracking-normal">
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

                  {/* 4. Người bệnh */}
                  <th scope="col" aria-sort={getAriaSort('nguoi_benh')}>
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className={cn(
                            HEADER_TRIGGER_CLASS,
                            sortField === 'nguoi_benh' && 'text-fg',
                          )}
                        >
                          <span>Người bệnh</span>
                          <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="start" className="w-48 p-1.5 text-xs normal-case tracking-normal">
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

                  {/* 5. Ngày sinh */}
                  <th scope="col" aria-sort={getAriaSort('ngay_sinh')}>
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className={cn(
                            HEADER_TRIGGER_CLASS,
                            sortField === 'ngay_sinh' && 'text-fg',
                          )}
                        >
                          <span>Ngày sinh</span>
                          <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="start" className="w-48 p-1.5 text-xs normal-case tracking-normal">
                        <SortMenuItems
                          field="ngay_sinh"
                          sortField={sortField}
                          sortDirection={sortDirection}
                          ascLabel="Cũ nhất trước"
                          descLabel="Mới nhất trước"
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
                      onChange={(values) => updateColumnFilters((prev) => ({ ...prev, khoa: values }))}
                    />
                  </th>

                  {/* 7. Chẩn đoán chính */}
                  <th scope="col" aria-sort={getAriaSort('chan_doan_chinh')}>
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className={cn(
                            HEADER_TRIGGER_CLASS,
                            sortField === 'chan_doan_chinh' && 'text-fg',
                          )}
                        >
                          <span>Chẩn đoán chính</span>
                          <ChevronDown className="size-3 shrink-0 opacity-70" aria-hidden="true" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="start" className="w-48 p-1.5 text-xs normal-case tracking-normal">
                        <SortMenuItems
                          field="chan_doan_chinh"
                          sortField={sortField}
                          sortDirection={sortDirection}
                          ascLabel="Chẩn đoán A → Z"
                          descLabel="Chẩn đoán Z → A"
                          onApplySort={handleApplySort}
                        />
                      </PopoverContent>
                    </Popover>
                  </th>

                  {/* 8. Trạng thái */}
                  <th scope="col" aria-sort={getAriaSort('trang_thai')}>
                    <ColumnFilterMenu
                      label="Trạng thái" field="trang_thai" align="end"
                      sortField={sortField} sortDirection={sortDirection}
                      ascLabel="Chưa duyệt → Đã duyệt" descLabel="Đã duyệt → Chưa duyệt" onApplySort={handleApplySort}
                      options={STATUS_OPTIONS} selected={statuses}
                      optionLabel={(value) => ORDER_STATUS_LABELS[value]}
                      onChange={(values) => updateColumnFilters((prev) => ({ ...prev, status: values }))}
                    />
                  </th>

                  {/* 9. Cảnh báo AI */}
                  <th scope="col" aria-sort={getAriaSort('ket_qua')}>
                    <ColumnFilterMenu
                      label="Cảnh báo AI" field="ket_qua" aliasField="uu_tien" align="end"
                      sortField={sortField} sortDirection={sortDirection}
                      ascLabel="Đạt trước" descLabel="Nghiêm trọng trước" onApplySort={handleApplySort}
                      options={WARNING_OPTIONS} selected={warnings}
                      optionLabel={(value) => ORDER_AI_WARNING_LABELS[value]}
                      onChange={(values) => updateColumnFilters((prev) => ({ ...prev, aiWarning: values }))}
                    />
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-line bg-surface">
                {pagedOrders.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <p className="text-sm font-medium text-fg">
                          Không có hồ sơ phù hợp bộ lọc hiện tại
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  pagedOrders.map((item) => {
                    const priorityLevel = getOrderPriorityLevel(item)
                    const priorityLabel = ORDER_PRIORITY_LABELS[priorityLevel]
                    const orderTime = item.thoi_diem_ke?.trim() || ''
                    const patientCode = getOrderPatientCode(item)
                    const hoTen = item.ho_ten?.trim() || ''
                    const patientSummary = item.nguoi_benh_tom_tat?.trim() || ''
                    const dobText = administrativeDate(item.ngay_sinh)
                    const department = item.khoa.trim()
                    const diagnosis = item.chan_doan_chinh?.trim() || ''
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
                        className="h-[44px] cursor-pointer transition-colors duration-120 hover:bg-surface-hover focus-within:bg-surface-hover focus-visible:bg-primary-soft/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
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
                          {orderTime ? (
                            <time
                              dateTime={orderTime}
                              title={formatReadableDateTime(orderTime)}
                            >
                              {formatReadableDateTime(orderTime)
                                .replace(/\/\d{4}$/, '')
                                .split(' · ')
                                .map((part, index) => (
                                  <span key={index} className="block leading-tight">
                                    {part}
                                  </span>
                                ))}
                            </time>
                          ) : (
                            <span className="font-sans text-fg-subtle">Chưa ghi nhận</span>
                          )}
                        </td>

                        {/* 3. Mã BN */}
                        <td
                          className="break-words font-mono text-xs whitespace-nowrap"
                          title={patientCode || undefined}
                        >
                          <button
                            type="button"
                            aria-label={`Mở hồ sơ ${patientCode || item.ca_id}`}
                            onClick={(event) => {
                              event.stopPropagation()
                              onOpenOrder(item.ca_id)
                            }}
                            className="cursor-pointer rounded-sm text-left text-primary underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                          >
                            {patientCode || '—'}
                          </button>
                        </td>

                        {/* 4. Người bệnh */}
                        <td
                          className="break-words text-sm text-fg"
                          title={patientSummary || hoTen || undefined}
                        >
                          {hoTen ? (
                            <>
                              <span className="block font-medium text-fg">
                                {hoTen.toLocaleUpperCase('vi-VN')}
                              </span>
                              {' '}
                            </>
                          ) : null}
                          <span className={hoTen ? 'block text-xs text-fg-muted' : patientSummary ? 'block' : 'block text-fg-subtle'}>
                            {patientSummary || 'Chưa ghi nhận'}
                          </span>
                        </td>

                        {/* 5. Ngày sinh */}
                        <td
                          className={cn(
                            'break-words text-sm tabular-nums',
                            dobText === 'Chưa ghi nhận' ? 'text-fg-subtle' : 'text-fg-muted',
                          )}
                        >
                          {dobText}
                        </td>

                        {/* 6. Khoa */}
                        <td className="break-words text-sm text-fg-muted" title={department || undefined}>
                          {department || '—'}
                        </td>

                        {/* 7. Chẩn đoán chính */}
                        <td
                          className={cn(
                            'break-words text-sm',
                            diagnosis ? 'text-fg' : 'text-fg-subtle',
                          )}
                          title={diagnosis || undefined}
                        >
                          {diagnosis || 'Chưa ghi nhận'}
                        </td>

                        {/* 8. Trạng thái */}
                        <td className="whitespace-nowrap" title={statusFullLabel}>
                          <Badge tone={STATUS_BADGE_TONE[workflowStatus]} variant="soft">
                            {statusShortLabel}
                          </Badge>
                        </td>

                        {/* 9. Cảnh báo AI (chỉ icon + tooltip khi hover) */}
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

          <TablePagination
            currentPage={pagination.currentPage}
            totalPages={pagination.totalPages}
            totalItems={pagination.totalItems}
            startIndex={pagination.startIndex}
            endIndex={pagination.endIndex}
            onPageChange={handlePageChange}
          />
        </>
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
