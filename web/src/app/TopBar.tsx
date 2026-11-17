import {
  ArrowLeft,
  ChevronRight,
  Menu,
  PanelRightClose,
  PanelRightOpen,
  Scale,
  Search,
  X,
} from 'lucide-react'
import type { RefObject } from 'react'
import { Link } from 'react-router-dom'
import type { CheDo } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { IconButton } from '@/components/ui/icon-button'
import { Kbd } from '@/components/ui/kbd'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

export interface TopBarProps {
  cheDo: CheDo | null
  activeOrderCode: string | null
  searchQuery: string
  searchInputRef: RefObject<HTMLInputElement | null>
  isDemoMode: boolean
  showSidebarTrigger: boolean
  sidebarOpen: boolean
  assistantOpen: boolean
  onToggleSidebar: () => void
  onToggleAssistant: () => void
  onSearchChange: (value: string) => void
  onSearchFocusOrSubmit: () => void
}

/** Thanh trên cùng của vùng giữa cao 48 px: đường dẫn, ô tìm kiếm, nhãn chế độ và nút mở/đóng trợ lý. */
export function TopBar({
  cheDo,
  activeOrderCode,
  searchQuery,
  searchInputRef,
  isDemoMode,
  showSidebarTrigger,
  sidebarOpen,
  assistantOpen,
  onToggleSidebar,
  onToggleAssistant,
  onSearchChange,
  onSearchFocusOrSubmit,
}: TopBarProps) {
  const isAiEnabled = Boolean(cheDo?.co_llm)

  return (
    <header
      className="workspace-toolbar flex min-h-11 shrink-0 flex-wrap items-center justify-between gap-x-2 gap-y-1 border-b border-line bg-canvas px-4 py-1.5"
      aria-label="Thanh công cụ bàn làm việc"
    >
      <div className="flex shrink-0 items-center gap-2">
        {showSidebarTrigger ? (
          <IconButton
            icon={<Menu className="size-4" strokeWidth={1.75} />}
            aria-label={sidebarOpen ? 'Đóng thanh điều hướng' : 'Mở thanh điều hướng'}
            aria-expanded={sidebarOpen}
            onClick={onToggleSidebar}
          />
        ) : null}

        {activeOrderCode ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/app"
                aria-label="Quay lại danh sách y lệnh"
                className="inline-flex size-7 items-center justify-center rounded-sm text-fg-muted transition-colors duration-120 hover:bg-surface-hover hover:text-fg"
              >
                <ArrowLeft className="size-4" strokeWidth={1.75} aria-hidden="true" />
              </Link>
            </TooltipTrigger>
            <TooltipContent side="bottom">Quay lại danh sách</TooltipContent>
          </Tooltip>
        ) : null}

        <nav aria-label="Đường dẫn" className="flex shrink-0 items-center gap-1.5 whitespace-nowrap text-sm">
          <Link
            to="/app"
            className={
              activeOrderCode
                ? 'text-fg-muted hover:text-fg transition-colors duration-120'
                : 'font-medium text-fg'
            }
          >
            Y lệnh
          </Link>
          {activeOrderCode ? (
            <>
              <ChevronRight
                className="size-3.5 shrink-0 text-fg-disabled"
                strokeWidth={1.75}
                aria-hidden="true"
              />
              <span className="font-mono text-xs font-semibold text-fg">
                {activeOrderCode}
              </span>
            </>
          ) : null}
        </nav>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <div className="toolbar-search relative items-center">
          <Search
            className="pointer-events-none absolute left-2.5 size-3.5 text-fg-subtle"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          <input
            ref={searchInputRef}
            type="search"
            value={searchQuery}
            aria-label="Tìm kiếm y lệnh"
            placeholder="Tìm ca, thuốc…"
            onFocus={onSearchFocusOrSubmit}
            onChange={(e) => {
              onSearchChange(e.target.value)
              onSearchFocusOrSubmit()
            }}
            className="h-7 w-52 lg:w-60 rounded-sm border border-line bg-surface pl-8 pr-14 text-xs text-fg placeholder:text-fg-subtle focus:border-primary"
          />
          {searchQuery ? (
            <button
              type="button"
              aria-label="Xoá từ khoá tìm kiếm"
              onClick={() => onSearchChange('')}
              className="absolute right-1.5 inline-flex size-5 cursor-pointer items-center justify-center rounded-sm text-fg-subtle hover:bg-surface-muted hover:text-fg"
            >
              <X className="size-3" strokeWidth={1.75} aria-hidden="true" />
            </button>
          ) : (
            <Kbd className="pointer-events-none absolute right-2">Ctrl K</Kbd>
          )}
        </div>

        <Badge tone="neutral" variant="soft" className="toolbar-mode border-transparent text-fg-subtle">
          Dữ liệu giả lập
        </Badge>

        <Badge
          tone={isAiEnabled ? 'ai' : 'neutral'}
          variant="soft"
          className="toolbar-mode border-transparent"
          icon={!isAiEnabled ? <Scale className="size-3.5" strokeWidth={1.75} /> : undefined}
        >
          {isAiEnabled ? 'AI bật' : 'Chỉ bộ luật'}
        </Badge>

        {isDemoMode ? (
          <Badge tone="neutral" variant="soft" className="border-transparent text-fg-subtle">
            Demo · không xác thực
          </Badge>
        ) : null}

        <IconButton
          icon={
            assistantOpen ? (
              <PanelRightClose className="size-4" strokeWidth={1.75} />
            ) : (
              <PanelRightOpen className="size-4" strokeWidth={1.75} />
            )
          }
          aria-label={assistantOpen ? 'Thu gọn trợ lý' : 'Mở trợ lý'}
          aria-expanded={assistantOpen}
          onClick={onToggleAssistant}
        />
      </div>
    </header>
  )
}
