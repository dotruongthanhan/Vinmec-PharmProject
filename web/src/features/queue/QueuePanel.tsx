import {
  CheckCheck,
  CircleCheck,
  CircleHelp,
  ClipboardList,
  FileQuestion,
  OctagonAlert,
  PanelLeftOpen,
  PanelLeftClose,
  TriangleAlert,
} from 'lucide-react'
import { useRef } from 'react'
import type { KeyboardEvent } from 'react'
import type { DongHangDoi, LoiNapCa } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { IconButton } from '@/components/ui/icon-button'
import { InlineAlert } from '@/components/ui/inline-alert'
import { ScrollArea } from '@/components/ui/scroll-area'
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'
import { stepQueueSelection } from '@/lib/queue'
import type { QueueFilter } from '@/lib/queue'

export interface QueuePanelProps {
  allCases: readonly DongHangDoi[]
  filteredCases: readonly DongHangDoi[]
  loiNap: readonly LoiNapCa[]
  loading: boolean
  error: string | null
  selectedCaseId: string | null
  filter: QueueFilter
  collapsed: boolean
  inDrawer?: boolean
  onSelectCase: (caId: string) => void
  onFilterChange: (filter: QueueFilter) => void
  onToggleCollapse: () => void
  onRetry: () => void
}

const PRIORITY_SOLID_CLASS: Record<DongHangDoi['uu_tien'], string> = {
  0: 'bg-danger-solid',
  1: 'bg-warning-solid',
  2: 'bg-offlabel-solid',
  3: 'bg-missing-solid',
  4: 'bg-success-solid',
}

/** Thanh bên hàng đợi y lệnh hỗ trợ lọc, chọn bàn phím và chế độ thu gọn 56 px. */
export function QueuePanel({
  allCases,
  filteredCases,
  loiNap,
  loading,
  error,
  selectedCaseId,
  filter,
  collapsed,
  inDrawer = false,
  onSelectCase,
  onFilterChange,
  onToggleCollapse,
  onRetry,
}: QueuePanelProps) {
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const handleListKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
      return
    }
    const direction = event.key === 'ArrowDown' ? 'down' : 'up'
    const nextId = stepQueueSelection(filteredCases, selectedCaseId, direction)
    if (!nextId) {
      return
    }
    event.preventDefault()
    onSelectCase(nextId)
    const targetBtn = itemRefs.current[nextId]
    if (targetBtn) {
      targetBtn.focus()
      targetBtn.scrollIntoView({ block: 'nearest' })
    }
  }

  if (collapsed && !inDrawer) {
    return (
      <div
        className="flex h-full w-full flex-col items-center py-3 gap-3"
        aria-label="Hàng đợi y lệnh đang thu gọn"
      >
        <IconButton
          icon={<PanelLeftOpen className="size-4" strokeWidth={1.75} />}
          aria-label="Mở rộng hàng đợi"
          tooltipSide="right"
          onClick={onToggleCollapse}
        />
        <div
          className="flex flex-1 min-h-0 w-full flex-col items-center gap-1.5 overflow-y-auto px-1 py-1"
          role="listbox"
          aria-label="Danh sách ca thu gọn"
          onKeyDown={handleListKeyDown}
        >
          {filteredCases.map((item) => {
            const isSelected = item.ca_id === selectedCaseId
            return (
              <Tooltip key={item.ca_id}>
                <TooltipTrigger asChild>
                  <button
                    ref={(el) => {
                      itemRefs.current[item.ca_id] = el
                    }}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    aria-label={`${item.ca_id} · ${item.khoa}`}
                    onClick={() => onSelectCase(item.ca_id)}
                    className="inline-flex size-7 min-h-7 min-w-7 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors duration-120 hover:bg-surface-hover"
                  >
                    <span
                      className={cn(
                        'size-3 rounded-full',
                        PRIORITY_SOLID_CLASS[item.uu_tien],
                        isSelected && 'ring-2 ring-primary ring-offset-2 ring-offset-surface',
                      )}
                    />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-60">
                  <div className="font-semibold">
                    {item.ca_id} · {item.khoa}
                  </div>
                  <div className="mt-0.5 line-clamp-2 opacity-90">{item.mo_ta}</div>
                </TooltipContent>
              </Tooltip>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full w-full flex-col min-h-0" aria-label="Hàng đợi y lệnh">
      <div
        className={cn(
          'flex items-center justify-between gap-2 px-3 py-3 border-b border-line shrink-0',
          inDrawer && 'pr-11',
        )}
      >
        <div className="flex items-center gap-2 min-w-0">
          <h2 className="text-sm font-semibold text-fg truncate">Y lệnh chờ thẩm định</h2>
          <Badge tone="neutral" variant="soft" className="tabular-nums shrink-0">
            {allCases.length}
          </Badge>
        </div>
        {!inDrawer ? (
          <IconButton
            icon={<PanelLeftClose className="size-4" strokeWidth={1.75} />}
            aria-label="Thu gọn hàng đợi"
            onClick={onToggleCollapse}
          />
        ) : null}
      </div>

      <div className="px-3 py-2 border-b border-line shrink-0">
        <SegmentedControl
          value={filter}
          onValueChange={(value) => onFilterChange(value as QueueFilter)}
          aria-label="Lọc hàng đợi"
          className="w-full"
        >
          <SegmentedControlItem value="tat_ca" className="flex-1">
            Tất cả
          </SegmentedControlItem>
          <SegmentedControlItem value="can_xem" className="flex-1">
            Cần xem
          </SegmentedControlItem>
          <SegmentedControlItem value="da_phan_hoi_het" className="flex-1">
            Đã phản hồi
          </SegmentedControlItem>
        </SegmentedControl>
      </div>

      <ScrollArea className="flex-1 min-h-0" viewportClassName="p-2.5">
        <div className="flex flex-col gap-2">
          {loiNap.length > 0 ? (
            <div className="flex flex-col gap-2 pb-1" role="alert" aria-label="Tệp ca bệnh bị lỗi">
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
              className="flex flex-col gap-2"
              aria-busy="true"
              aria-label="Đang tải hàng đợi"
            >
              <Skeleton className="h-[76px] w-full" />
              <Skeleton className="h-[76px] w-full" />
              <Skeleton className="h-[76px] w-full" />
              <Skeleton className="h-[76px] w-full" />
              <Skeleton className="h-[76px] w-full" />
            </div>
          ) : null}

          {!loading && error ? (
            <InlineAlert
              tone="danger"
              role="alert"
              title="Không tải được hàng đợi"
              action={
                <Button variant="secondary" size="sm" onClick={onRetry}>
                  Thử lại
                </Button>
              }
            >
              <span className="whitespace-pre-wrap break-words text-xs">{error}</span>
            </InlineAlert>
          ) : null}

          {!loading && !error && allCases.length === 0 ? (
            <EmptyState icon={ClipboardList} title="Không có y lệnh chờ thẩm định" />
          ) : null}

          {!loading && !error && allCases.length > 0 && filteredCases.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="Không có ca phù hợp bộ lọc"
              description="Thử chuyển sang bộ lọc Tất cả để xem toàn bộ danh sách."
            />
          ) : null}

          {!loading && !error && filteredCases.length > 0 ? (
            <div
              className="flex flex-col gap-2"
              role="listbox"
              aria-label="Danh sách ca thẩm định"
              onKeyDown={handleListKeyDown}
            >
              {filteredCases.map((item) => {
                const isSelected = item.ca_id === selectedCaseId
                const hasAnyCount =
                  item.so_nghiem_trong > 0 ||
                  item.so_can_luu_y > 0 ||
                  item.so_thieu_du_lieu > 0

                return (
                  <button
                    key={item.ca_id}
                    ref={(el) => {
                      itemRefs.current[item.ca_id] = el
                    }}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => onSelectCase(item.ca_id)}
                    className={cn(
                      'relative w-full text-left min-h-[76px] p-3 pl-4 rounded-md border transition-colors duration-120 cursor-pointer flex flex-col gap-1.5',
                      isSelected
                        ? 'bg-primary-soft border-primary-line shadow-xs'
                        : 'bg-surface border-line/70 hover:bg-surface-hover hover:border-line',
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        'absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full',
                        PRIORITY_SOLID_CLASS[item.uu_tien],
                      )}
                    />

                    <div className="flex items-center justify-between gap-2 min-w-0">
                      <span className="text-sm font-semibold text-fg shrink-0">{item.ca_id}</span>
                      <span className="text-xs text-fg-subtle truncate">{item.khoa}</span>
                    </div>

                    <div className="flex items-center gap-1.5 flex-wrap">
                      {item.so_nghiem_trong > 0 ? (
                        <Badge
                          tone="danger"
                          variant="soft"
                          icon={<OctagonAlert className="size-3.5" strokeWidth={1.75} />}
                          className="tabular-nums"
                        >
                          {item.so_nghiem_trong} nghiêm trọng
                        </Badge>
                      ) : null}
                      {item.so_can_luu_y > 0 ? (
                        <Badge
                          tone="warning"
                          variant="soft"
                          icon={<TriangleAlert className="size-3.5" strokeWidth={1.75} />}
                          className="tabular-nums"
                        >
                          {item.so_can_luu_y} cần lưu ý
                        </Badge>
                      ) : null}
                      {item.so_thieu_du_lieu > 0 ? (
                        <Badge
                          tone="missing"
                          variant="soft"
                          icon={<CircleHelp className="size-3.5" strokeWidth={1.75} />}
                          className="tabular-nums"
                        >
                          {item.so_thieu_du_lieu} thiếu dữ liệu
                        </Badge>
                      ) : null}
                      {!hasAnyCount && item.uu_tien === 2 ? (
                        <Badge
                          tone="offlabel"
                          variant="soft"
                          icon={<FileQuestion className="size-3.5" strokeWidth={1.75} />}
                        >
                          Ngoài HDSD
                        </Badge>
                      ) : null}
                      {!hasAnyCount && item.uu_tien !== 2 ? (
                        <Badge
                          tone="success"
                          variant="soft"
                          icon={<CircleCheck className="size-3.5" strokeWidth={1.75} />}
                        >
                          Đạt
                        </Badge>
                      ) : null}

                      {item.da_phan_hoi_het ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="ml-auto inline-flex items-center">
                              <CheckCheck
                                className="size-4 text-success-fg shrink-0"
                                strokeWidth={1.75}
                                aria-label="Đã phản hồi hết"
                              />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>Đã phản hồi hết các nhận định</TooltipContent>
                        </Tooltip>
                      ) : null}
                    </div>

                    <p className="text-sm text-fg-muted line-clamp-2 whitespace-normal">
                      {item.mo_ta}
                    </p>
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>
      </ScrollArea>
    </div>
  )
}
