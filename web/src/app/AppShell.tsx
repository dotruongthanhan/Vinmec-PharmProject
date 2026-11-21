import { X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { KeyboardEvent, PointerEvent as ReactPointerEvent, ReactNode, RefObject } from 'react'
import type { CheDo } from '@/api/types'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { IconButton } from '@/components/ui/icon-button'
import { cn } from '@/lib/cn'
import { ASSISTANT_MAX_WIDTH, ASSISTANT_MIN_WIDTH, clampAssistantWidth } from '@/lib/prefs'
import { TopBar } from './TopBar'

export interface AppShellProps {
  cheDo: CheDo | null
  activeOrderCode: string | null
  breadcrumbLabel?: string
  backTo?: string
  /** false ở các trang tra cứu: không có khung trợ lý và ô tìm hồ sơ. */
  assistantAvailable?: boolean
  searchQuery: string
  searchInputRef: RefObject<HTMLInputElement | null>
  isDemoMode: boolean
  sidebarCollapsed: boolean
  assistantCollapsed: boolean
  assistantWidth: number
  drawerSidebarOpen: boolean
  drawerAssistantOpen: boolean
  onDrawerSidebarChange: (open: boolean) => void
  onDrawerAssistantChange: (open: boolean) => void
  onToggleSidebar: () => void
  onToggleAssistant: () => void
  onAssistantWidthChange: (width: number) => void
  onSearchChange: (value: string) => void
  onSearchFocusOrSubmit: () => void
  sidebarSlot: ReactNode
  sidebarDrawerSlot: ReactNode
  assistantSlot: ReactNode
  children: ReactNode
}

function getMediaMatch(query: string): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(query).matches
}

function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
        return () => {}
      }
      const mql = window.matchMedia(query)
      if (typeof mql.addEventListener === 'function') {
        mql.addEventListener('change', onStoreChange)
        return () => {
          mql.removeEventListener('change', onStoreChange)
        }
      }
      return () => {}
    },
    () => getMediaMatch(query),
    () => false,
  )
}

/** Khung bố cục 3 cột mới: thanh bên nền tối (248/56), vùng giữa co giãn, trợ lý kéo đổi rộng (320–560). */
export function AppShell({
  cheDo,
  activeOrderCode,
  breadcrumbLabel,
  backTo,
  assistantAvailable = true,
  searchQuery,
  searchInputRef,
  isDemoMode,
  sidebarCollapsed,
  assistantCollapsed,
  assistantWidth,
  drawerSidebarOpen,
  drawerAssistantOpen,
  onDrawerSidebarChange,
  onDrawerAssistantChange,
  onToggleSidebar,
  onToggleAssistant,
  onAssistantWidthChange,
  onSearchChange,
  onSearchFocusOrSubmit,
  sidebarSlot,
  sidebarDrawerSlot,
  assistantSlot,
  children,
}: AppShellProps) {
  const isCompactAssistant = useMediaQuery('(max-width: 1179px)')
  const isCompactSidebar = useMediaQuery('(max-width: 899px)')

  const [liveDragWidth, setLiveDragWidth] = useState<number | null>(null)
  const dragWidthRef = useRef<number>(assistantWidth)

  useEffect(() => {
    if (!isCompactSidebar && drawerSidebarOpen) {
      onDrawerSidebarChange(false)
    }
  }, [isCompactSidebar, drawerSidebarOpen, onDrawerSidebarChange])

  useEffect(() => {
    if (!isCompactAssistant && drawerAssistantOpen) {
      onDrawerAssistantChange(false)
    }
  }, [isCompactAssistant, drawerAssistantOpen, onDrawerAssistantChange])

  const sidebarOpen = isCompactSidebar ? drawerSidebarOpen : !sidebarCollapsed
  const assistantOpen = assistantAvailable && (isCompactAssistant ? drawerAssistantOpen : !assistantCollapsed)

  const handleToggleSidebar = useCallback(() => {
    if (isCompactSidebar) {
      onDrawerSidebarChange(!drawerSidebarOpen)
      return
    }
    onToggleSidebar()
  }, [isCompactSidebar, drawerSidebarOpen, onDrawerSidebarChange, onToggleSidebar])

  const handleToggleAssistant = useCallback(() => {
    if (isCompactAssistant) {
      onDrawerAssistantChange(!drawerAssistantOpen)
      return
    }
    onToggleAssistant()
  }, [isCompactAssistant, drawerAssistantOpen, onDrawerAssistantChange, onToggleAssistant])

  const isDragging = liveDragWidth !== null

  useEffect(() => {
    if (!isDragging) {
      return
    }
    const handleMove = (event: PointerEvent) => {
      const next = clampAssistantWidth(window.innerWidth - event.clientX)
      dragWidthRef.current = next
      setLiveDragWidth(next)
    }
    const handleUp = () => {
      onAssistantWidthChange(dragWidthRef.current)
      setLiveDragWidth(null)
    }
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp, { once: true })
    return () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
    }
  }, [isDragging, onAssistantWidthChange])

  const handleStartResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    const current = clampAssistantWidth(assistantWidth)
    dragWidthRef.current = current
    setLiveDragWidth(current)
  }

  const handleResizeKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      onAssistantWidthChange(clampAssistantWidth(assistantWidth + 16))
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      onAssistantWidthChange(clampAssistantWidth(assistantWidth - 16))
    }
  }

  const effectiveAssistantWidth = liveDragWidth ?? assistantWidth

  return (
    <div className="flex h-screen w-full overflow-hidden bg-canvas text-fg">
      {/* Cột 1: Thanh bên điều hướng nền tối */}
      {!isCompactSidebar ? (
        <aside
          aria-label="Thanh bên điều hướng"
          className={cn(
            'shrink-0 overflow-hidden border-r border-ink-line bg-ink transition-[width] duration-180 ease-out',
            sidebarCollapsed ? 'w-[56px]' : 'w-[248px]',
          )}
        >
          {sidebarSlot}
        </aside>
      ) : null}

      {/* Cột 2: Vùng giữa (thanh trên 48px + nội dung tự cuộn + chân trang) */}
      <div className="workspace-center flex flex-1 min-w-0 flex-col overflow-hidden">
        <TopBar
          cheDo={cheDo}
          activeOrderCode={activeOrderCode}
          breadcrumbLabel={breadcrumbLabel}
          backTo={backTo}
          showAssistantToggle={assistantAvailable}
          showSearch={assistantAvailable}
          searchQuery={searchQuery}
          searchInputRef={searchInputRef}
          isDemoMode={isDemoMode}
          showSidebarTrigger={isCompactSidebar}
          sidebarOpen={sidebarOpen}
          assistantOpen={assistantOpen}
          onToggleSidebar={handleToggleSidebar}
          onToggleAssistant={handleToggleAssistant}
          onSearchChange={onSearchChange}
          onSearchFocusOrSubmit={onSearchFocusOrSubmit}
        />

        <main
          aria-label="Vùng làm việc chính"
          className="flex flex-1 min-h-0 min-w-0 flex-col overflow-y-auto overscroll-contain scroll-pt-14"
        >
          <div className="flex-1">{children}</div>

          <footer className="mt-auto border-t border-line/70 bg-canvas px-5 py-2.5 text-xs text-fg-subtle">
            Kết quả tham khảo. Dược sĩ kiểm chứng và quyết định.
          </footer>
        </main>
      </div>

      {/* Cột 3: Trợ lý AI kéo đổi chiều rộng */}
      {assistantAvailable && !isCompactAssistant && !assistantCollapsed ? (
        <aside
          aria-label="Khung trợ lý AI"
          style={{ width: `${effectiveAssistantWidth}px` }}
          className={cn('relative flex shrink-0 border-l border-line bg-surface', sidebarCollapsed ? 'max-w-[calc(100vw-616px)]' : 'max-w-[calc(100vw-808px)]')}
        >
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Kéo để đổi chiều rộng khung trợ lý"
            aria-valuemin={ASSISTANT_MIN_WIDTH}
            aria-valuemax={ASSISTANT_MAX_WIDTH}
            aria-valuenow={effectiveAssistantWidth}
            tabIndex={0}
            onPointerDown={handleStartResize}
            onKeyDown={handleResizeKeyDown}
            className="absolute inset-y-0 -left-1 z-20 w-2 cursor-col-resize hover:bg-primary/25 focus-visible:bg-primary/40"
          />
          <div className="flex h-full w-full min-w-0 flex-col">{assistantSlot}</div>
        </aside>
      ) : null}

      {/* Ngăn trượt trái cho thanh bên (< 900px) */}
      <Dialog open={isCompactSidebar && drawerSidebarOpen} onOpenChange={onDrawerSidebarChange}>
        <DialogContent
          variant="drawer-left"
          tabIndex={-1}
          className="w-[248px] border-ink-line bg-ink p-0"
          onOpenAutoFocus={(e) => {
            e.preventDefault()
            if (e.currentTarget instanceof HTMLElement) {
              e.currentTarget.focus()
            }
          }}
        >
          <DialogTitle className="sr-only">Điều hướng bàn làm việc</DialogTitle>
          <DialogDescription className="sr-only">
            Các bộ lọc y lệnh, khoa và hội thoại gần đây
          </DialogDescription>
          <div className="relative flex h-full min-h-0 flex-col">
            <DialogClose asChild>
              <IconButton
                icon={<X className="size-4 text-ink-muted" strokeWidth={1.75} />}
                aria-label="Đóng thanh điều hướng"
                className="absolute right-2.5 top-2.5 z-10 hover:bg-ink-soft hover:text-ink-fg"
              />
            </DialogClose>
            {sidebarDrawerSlot}
          </div>
        </DialogContent>
      </Dialog>

      {/* Ngăn trượt phải cho trợ lý (< 1180px) */}
      <Dialog
        open={assistantAvailable && isCompactAssistant && drawerAssistantOpen}
        onOpenChange={onDrawerAssistantChange}
      >
        <DialogContent
          variant="drawer-right"
          tabIndex={-1}
          className="w-[400px] p-0"
          onOpenAutoFocus={(e) => {
            e.preventDefault()
            if (e.currentTarget instanceof HTMLElement) {
              e.currentTarget.focus()
            }
          }}
        >
          <DialogTitle className="sr-only">Trợ lý AI</DialogTitle>
          <DialogDescription className="sr-only">
            Khung hỏi đáp về ca bệnh đang mở và tra cứu đoạn nguồn
          </DialogDescription>
          <div className="flex h-full min-h-0 flex-col">{assistantSlot}</div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
