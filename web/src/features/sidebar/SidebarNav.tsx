import {
  ChevronsUpDown,
  CircleHelp,
  ClipboardList,
  FileText,
  LogIn,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
} from 'lucide-react'
import { useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { VinmecLogo } from '@/components/VinmecLogo'
import type { AuthRole } from '@/features/auth/authClient'
import { cn } from '@/lib/cn'
import type {
  OrderGroupCounts,
  OrderSelectionFilter,
} from '@/lib/orders'

export interface SidebarNavProps {
  counts: OrderGroupCounts
  activeFilter: OrderSelectionFilter
  collapsed: boolean
  inDrawer?: boolean
  activeSection: 'orders' | 'records'
  onNavigate: () => void
  userEmail: string | null
  vaiTro?: AuthRole | null
  isDemoMode: boolean
  onSelectFilter: (filter: OrderSelectionFilter) => void
  onToggleCollapse: () => void
  onOpenSettings: () => void
  onSignIn: () => void
  onSignOut: (options?: { scope?: 'local' | 'global' }) => void
}

/** Thanh bên điều hướng nền tối (248 px, thu gọn còn 56 px). */
export function SidebarNav({
  collapsed,
  inDrawer = false,
  activeSection,
  onNavigate,
  userEmail,
  vaiTro,
  isDemoMode,
  onToggleCollapse,
  onOpenSettings,
  onSignIn,
  onSignOut,
}: SidebarNavProps) {
  const effectiveCollapsed = collapsed && !inDrawer
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)

  const accountLabel = isDemoMode ? 'Chế độ demo · chưa đăng nhập' : (userEmail ?? 'Tài khoản')
  const shortAccountName = isDemoMode
    ? 'demo'
    : (userEmail?.split('@')[0]?.trim() || 'Tài khoản')
  const accountInitial = shortAccountName.slice(0, 1).toUpperCase() || 'D'
  const accountTierLabel = isDemoMode
    ? 'Demo'
    : vaiTro === 'admin'
      ? 'Quản trị'
      : vaiTro === 'duoc_si_ls'
        ? 'Dược sĩ lâm sàng'
        : 'Chưa cấp quyền'

  const handleAccountMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(
      event.currentTarget.querySelectorAll<HTMLButtonElement>('button[role="menuitem"]'),
    )
    if (items.length === 0) {
      return
    }
    const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement)
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      items[(currentIndex + 1 + items.length) % items.length]?.focus()
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      items[(currentIndex - 1 + items.length) % items.length]?.focus()
    } else if (event.key === 'Home') {
      event.preventDefault()
      items[0]?.focus()
    } else if (event.key === 'End') {
      event.preventDefault()
      items[items.length - 1]?.focus()
    }
  }

  return (
    <nav
      aria-label="Điều hướng bàn làm việc"
      className="flex h-full w-full flex-col bg-ink text-ink-fg select-none"
    >
      {/* 1. Tên sản phẩm và nút thu gọn */}
      <div
        className={cn(
          'flex h-11 shrink-0 items-center border-b border-ink-line',
          effectiveCollapsed ? 'justify-center px-2' : 'justify-between gap-2 px-3',
          inDrawer && 'pr-11',
        )}
      >
        {!effectiveCollapsed ? (
          <span className="flex min-w-0 items-center gap-2">
            <VinmecLogo alwaysOnDark imageClassName="h-9" />
            <span className="truncate text-sm font-semibold tracking-tight text-ink-fg">
              Thẩm định y lệnh
            </span>
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

      {/* 2. Hai mục điều hướng chính */}
      <div className="flex shrink-0 flex-col gap-1 p-2">
        {([
          { section: 'orders', to: '/app', label: 'Y lệnh', icon: ClipboardList },
          { section: 'records', to: '/app/ho-so', label: 'Hồ sơ bệnh án', icon: FileText },
        ] as const).map(({ section, to, label, icon: Icon }) => {
          const link = (
            <Link
              to={to}
              aria-label={label}
              aria-current={activeSection === section ? 'page' : undefined}
              onClick={onNavigate}
              className={cn(
                'flex h-9 min-w-0 items-center gap-2 rounded-sm text-sm transition-colors duration-120 hover:bg-ink-soft hover:text-ink-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
                effectiveCollapsed ? 'justify-center' : 'px-3',
                activeSection === section ? 'bg-ink-soft font-semibold text-ink-fg' : 'text-ink-muted',
              )}
            >
              <Icon className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
              {!effectiveCollapsed ? <span>{label}</span> : null}
            </Link>
          )
          return effectiveCollapsed ? (
            <Tooltip key={section}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
          ) : <div key={section}>{link}</div>
        })}
      </div>

      <div className="flex-1 min-h-0" aria-hidden="true" />

      {/* 4. Đáy: thanh hồ sơ gọn và nút Cài đặt kiểu Claude Desktop */}
      <div
        className={cn(
          'border-t border-ink-line px-2 py-2 shrink-0 flex items-center gap-1',
          effectiveCollapsed ? 'flex-col justify-center' : 'justify-between',
        )}
      >
        <Popover open={accountMenuOpen} onOpenChange={setAccountMenuOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              aria-label={effectiveCollapsed ? `${accountLabel} · Tuỳ chọn tài khoản` : 'Mở menu tài khoản và cài đặt'}
              aria-haspopup="menu"
              aria-expanded={accountMenuOpen}
              className={cn(
                'flex min-w-0 cursor-pointer items-center rounded-sm text-left transition-colors duration-120 hover:bg-ink-soft',
                effectiveCollapsed
                  ? 'size-9 justify-center'
                  : 'h-9 flex-1 gap-2 px-2',
              )}
            >
              <span
                aria-hidden="true"
                className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-on-primary"
              >
                {accountInitial}
              </span>
              {!effectiveCollapsed ? (
                <>
                  <span className="min-w-0 flex-1 truncate text-sm text-ink-fg">
                    <span className="font-medium">{shortAccountName}</span>
                    <span className="text-ink-muted"> · {accountTierLabel}</span>
                  </span>
                  <ChevronsUpDown
                    className="size-3.5 shrink-0 text-ink-muted"
                    strokeWidth={1.75}
                    aria-hidden="true"
                  />
                </>
              ) : null}
            </button>
          </PopoverTrigger>

          <PopoverContent
            side={effectiveCollapsed ? 'right' : 'top'}
            align="start"
            sideOffset={8}
            className="w-64 p-1.5 border-line-strong bg-surface-raised shadow-xl"
          >
            <div
              role="menu"
              aria-label="Menu tài khoản và cài đặt"
              onKeyDown={handleAccountMenuKeyDown}
              className="flex flex-col"
            >
              <div
                className="truncate px-2.5 py-2 text-xs text-fg-muted"
                title={accountLabel}
              >
                {accountLabel}
              </div>

              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setAccountMenuOpen(false)
                  onOpenSettings()
                }}
                className="flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 text-left text-sm text-fg transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-surface-hover"
              >
                <Settings className="size-4 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                <span className="flex-1">Cài đặt</span>
                <span className="font-mono text-xs text-fg-subtle" aria-hidden="true">
                  Ctrl+,
                </span>
              </button>

              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setAccountMenuOpen(false)
                  onOpenSettings()
                }}
                className="flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 text-left text-sm text-fg transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-surface-hover"
              >
                <CircleHelp className="size-4 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                <span className="flex-1">Trợ giúp & Phím tắt</span>
              </button>

              <hr className="my-1 border-line" />

              {isDemoMode ? (
                <>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setAccountMenuOpen(false)
                      onSignIn()
                    }}
                    className="flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 text-left text-sm text-fg transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-surface-hover"
                  >
                    <LogIn className="size-4 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                    <span className="flex-1">Đăng nhập tài khoản</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setAccountMenuOpen(false)
                      onSignOut()
                    }}
                    className="flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 text-left text-sm text-fg transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-surface-hover"
                  >
                    <LogOut className="size-4 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                    <span className="flex-1">Thoát chế độ demo</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setAccountMenuOpen(false)
                      onSignOut({ scope: 'local' })
                    }}
                    className="flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 text-left text-sm text-fg transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-surface-hover"
                  >
                    <LogOut className="size-4 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                    <span className="flex-1">Đăng xuất</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setAccountMenuOpen(false)
                      onSignOut({ scope: 'global' })
                    }}
                    className="flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 text-left text-sm text-fg transition-colors duration-120 hover:bg-surface-hover focus-visible:bg-surface-hover"
                  >
                    <LogOut className="size-4 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                    <span className="flex-1">Đăng xuất mọi thiết bị</span>
                  </button>
                </>
              )}
            </div>
          </PopoverContent>
        </Popover>

        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label="Cài đặt (Ctrl+,)"
              onClick={onOpenSettings}
              className="inline-flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-sm text-ink-muted transition-colors duration-120 hover:bg-ink-soft hover:text-ink-fg"
            >
              <Settings className="size-4" strokeWidth={1.75} aria-hidden="true" />
            </button>
          </TooltipTrigger>
          <TooltipContent side={effectiveCollapsed ? 'right' : 'top'}>
            Cài đặt (Ctrl+,)
          </TooltipContent>
        </Tooltip>
      </div>
    </nav>
  )
}
