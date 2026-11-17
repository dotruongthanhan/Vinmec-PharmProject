import {
  Building2,
  CheckCheck,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  ClipboardList,
  LogOut,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { DongHangDoi } from '@/api/types'
import { Kbd } from '@/components/ui/kbd'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ThemeControl } from '@/features/theme/ThemeControl'
import { cn } from '@/lib/cn'
import type {
  OrderFilterGroup,
  OrderGroupCounts,
  OrderSelectionFilter,
} from '@/lib/orders'

export interface SidebarNavProps {
  counts: OrderGroupCounts
  activeFilter: OrderSelectionFilter
  isListRoute: boolean
  activeCaseId: string | null
  recentCases: readonly DongHangDoi[]
  collapsed: boolean
  inDrawer?: boolean
  userEmail: string | null
  isDemoMode: boolean
  onSelectFilter: (filter: OrderSelectionFilter) => void
  onOpenCase: (caId: string) => void
  onFocusSearch: () => void
  onToggleCollapse: () => void
  onSignOut: () => void
}

interface GroupNavSpec {
  group: OrderFilterGroup
  label: string
  count: number
  icon: ReactNode
}

function SidebarActionButton({
  active = false,
  collapsed,
  icon,
  label,
  trailing,
  tooltipLabel,
  onClick,
}: {
  active?: boolean
  collapsed: boolean
  icon: ReactNode
  label: string
  trailing?: ReactNode
  tooltipLabel?: string
  onClick: () => void
}) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      aria-label={collapsed ? (tooltipLabel ?? label) : undefined}
      className={cn(
        'relative flex w-full cursor-pointer items-center rounded-sm text-left text-sm transition-colors duration-120',
        collapsed ? 'h-9 justify-center px-0' : 'h-8 gap-2.5 px-2.5',
        active
          ? 'bg-ink-soft font-medium text-ink-fg'
          : 'text-ink-muted hover:bg-ink-soft/70 hover:text-ink-fg',
      )}
    >
      {active ? (
        <span
          aria-hidden="true"
          className="absolute inset-y-1 left-0 w-0.5 rounded-r-full bg-primary"
        />
      ) : null}
      <span className="inline-flex size-4 shrink-0 items-center justify-center" aria-hidden="true">
        {icon}
      </span>
      {!collapsed ? (
        <>
          <span className="min-w-0 flex-1 truncate">{label}</span>
          {trailing}
        </>
      ) : null}
    </button>
  )

  if (!collapsed) {
    return button
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="right">{tooltipLabel ?? label}</TooltipContent>
    </Tooltip>
  )
}

/** Thanh bên điều hướng tính năng nền tối (248 px, thu gọn còn 56 px). */
export function SidebarNav({
  counts,
  activeFilter,
  isListRoute,
  activeCaseId,
  recentCases,
  collapsed,
  inDrawer = false,
  userEmail,
  isDemoMode,
  onSelectFilter,
  onOpenCase,
  onFocusSearch,
  onToggleCollapse,
  onSignOut,
}: SidebarNavProps) {
  const effectiveCollapsed = collapsed && !inDrawer

  const groupItems: GroupNavSpec[] = [
    {
      group: 'tat_ca',
      label: 'Tất cả',
      count: counts.tat_ca,
      icon: <ClipboardList className="size-4" strokeWidth={1.75} />,
    },
    {
      group: 'can_xem',
      label: 'Cần xem',
      count: counts.can_xem,
      icon: <CircleAlert className="size-4" strokeWidth={1.75} />,
    },
    {
      group: 'thieu_du_lieu',
      label: 'Thiếu dữ liệu',
      count: counts.thieu_du_lieu,
      icon: <CircleHelp className="size-4" strokeWidth={1.75} />,
    },
    {
      group: 'dat',
      label: 'Đạt',
      count: counts.dat,
      icon: <CircleCheck className="size-4" strokeWidth={1.75} />,
    },
    {
      group: 'da_phan_hoi',
      label: 'Đã phản hồi',
      count: counts.da_phan_hoi,
      icon: <CheckCheck className="size-4" strokeWidth={1.75} />,
    },
  ]

  const accountLabel = isDemoMode ? 'Chế độ demo' : (userEmail ?? 'Dược sĩ')

  return (
    <nav
      aria-label="Điều hướng bàn làm việc"
      className="flex h-full w-full flex-col bg-ink text-ink-fg select-none"
    >
      {/* 1. Tên sản phẩm và nút thu gọn */}
      <div
        className={cn(
          'flex h-12 shrink-0 items-center border-b border-ink-line',
          effectiveCollapsed ? 'justify-center px-2' : 'justify-between gap-2 px-3',
          inDrawer && 'pr-11',
        )}
      >
        {!effectiveCollapsed ? (
          <span className="truncate text-sm font-semibold tracking-tight text-ink-fg">
            Thẩm định y lệnh
          </span>
        ) : null}

        {!inDrawer ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label={effectiveCollapsed ? 'Mở rộng thanh điều hướng' : 'Thu gọn thanh điều hướng'}
                onClick={onToggleCollapse}
                className="inline-flex size-7 min-h-7 min-w-7 cursor-pointer items-center justify-center rounded-sm text-ink-muted transition-colors duration-120 hover:bg-ink-soft hover:text-ink-fg"
              >
                {effectiveCollapsed ? (
                  <PanelLeftOpen className="size-4" strokeWidth={1.75} aria-hidden="true" />
                ) : (
                  <PanelLeftClose className="size-4" strokeWidth={1.75} aria-hidden="true" />
                )}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {effectiveCollapsed ? 'Mở rộng thanh điều hướng' : 'Thu gọn thanh điều hướng'}
            </TooltipContent>
          </Tooltip>
        ) : null}
      </div>

      {/* 2. Tìm kiếm (Ctrl K) */}
      <div className="border-b border-ink-line px-2.5 py-2.5 shrink-0">
        <SidebarActionButton
          collapsed={effectiveCollapsed}
          icon={<Search className="size-4" strokeWidth={1.75} />}
          label="Tìm kiếm"
          tooltipLabel="Tìm kiếm (Ctrl K)"
          trailing={
            <Kbd className="border-ink-line bg-ink-soft text-ink-muted">Ctrl K</Kbd>
          }
          onClick={onFocusSearch}
        />
      </div>

      {/* 3-5. Nhóm Y lệnh, Theo khoa, Hội thoại gần đây */}
      <ScrollArea className="flex-1 min-h-0" viewportClassName="px-2.5 py-3">
        <div className="flex flex-col gap-5">
          {/* 3. Nhóm Y lệnh */}
          <div className="flex flex-col gap-1">
            {!effectiveCollapsed ? (
              <div className="px-2.5 pb-1 text-2xs font-medium uppercase tracking-[0.04em] text-ink-muted">
                Y lệnh
              </div>
            ) : null}
            {groupItems.map((item) => {
              const isSelected =
                isListRoute &&
                activeFilter.type === 'group' &&
                activeFilter.group === item.group

              return (
                <SidebarActionButton
                  key={item.group}
                  active={isSelected}
                  collapsed={effectiveCollapsed}
                  icon={item.icon}
                  label={item.label}
                  tooltipLabel={`${item.label} (${item.count})`}
                  trailing={
                    <span className="font-mono text-xs text-ink-muted tabular-nums">
                      {item.count}
                    </span>
                  }
                  onClick={() => onSelectFilter({ type: 'group', group: item.group })}
                />
              )
            })}
          </div>

          {/* 4. Nhóm Theo khoa */}
          {counts.departments.length > 0 ? (
            <div className="flex flex-col gap-1">
              {!effectiveCollapsed ? (
                <div className="px-2.5 pb-1 text-2xs font-medium uppercase tracking-[0.04em] text-ink-muted">
                  Theo khoa
                </div>
              ) : null}
              {counts.departments.map((dept) => {
                const isSelected =
                  isListRoute &&
                  activeFilter.type === 'khoa' &&
                  activeFilter.khoa === dept.khoa

                return (
                  <SidebarActionButton
                    key={dept.khoa}
                    active={isSelected}
                    collapsed={effectiveCollapsed}
                    icon={<Building2 className="size-4" strokeWidth={1.75} />}
                    label={dept.khoa}
                    tooltipLabel={`${dept.khoa} (${dept.count})`}
                    trailing={
                      <span className="font-mono text-xs text-ink-muted tabular-nums">
                        {dept.count}
                      </span>
                    }
                    onClick={() => onSelectFilter({ type: 'khoa', khoa: dept.khoa })}
                  />
                )
              })}
            </div>
          ) : null}

          {/* 5. Nhóm Hội thoại gần đây (ẩn hoàn toàn nếu chưa có ca nào được hỏi) */}
          {recentCases.length > 0 ? (
            <div className="flex flex-col gap-1">
              {!effectiveCollapsed ? (
                <div className="px-2.5 pb-1 text-2xs font-medium uppercase tracking-[0.04em] text-ink-muted">
                  Hội thoại gần đây
                </div>
              ) : null}
              {recentCases.map((c) => {
                const isSelected = !isListRoute && activeCaseId === c.ca_id
                return (
                  <SidebarActionButton
                    key={c.ca_id}
                    active={isSelected}
                    collapsed={effectiveCollapsed}
                    icon={<MessageSquareText className="size-4" strokeWidth={1.75} />}
                    label={c.ca_id}
                    tooltipLabel={`${c.ca_id} · ${c.khoa}`}
                    trailing={
                      <span className="truncate max-w-24 text-2xs text-ink-muted">{c.khoa}</span>
                    }
                    onClick={() => onOpenCase(c.ca_id)}
                  />
                )
              })}
            </div>
          ) : null}
        </div>
      </ScrollArea>

      {/* 6. Đáy: tài khoản và nút Đăng xuất */}
      <div className="border-t border-ink-line px-2.5 py-2.5 shrink-0 flex flex-col gap-1">
        <ThemeControl collapsed={effectiveCollapsed} inSidebar />
        {!effectiveCollapsed ? (
          <div
            className="truncate px-2.5 py-1 text-xs text-ink-muted"
            title={accountLabel}
          >
            {accountLabel}
          </div>
        ) : null}
        <SidebarActionButton
          collapsed={effectiveCollapsed}
          icon={<LogOut className="size-4" strokeWidth={1.75} />}
          label="Đăng xuất"
          tooltipLabel={`${accountLabel} · Đăng xuất`}
          onClick={onSignOut}
        />
      </div>
    </nav>
  )
}
