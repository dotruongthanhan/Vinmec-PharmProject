import { X } from 'lucide-react'
import { useState, useSyncExternalStore } from 'react'
import type { ReactNode } from 'react'
import type { CheDo } from '@/api/types'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { IconButton } from '@/components/ui/icon-button'
import { Toaster } from '@/components/ui/toaster'
import { TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'
import { TopBar } from './TopBar'

export interface AppShellProps {
  cheDo: CheDo | null
  queueCollapsed: boolean
  onToggleQueue: () => void
  chatCollapsed: boolean
  onToggleChat: () => void
  hasCase: boolean
  thoiGianMs?: number | null
  queueSlot: ReactNode
  queueDrawerSlot?: ReactNode
  headerSlot: ReactNode | null
  children: ReactNode
  chatSlot?: ReactNode | null
  renderChat?: (onClose: () => void) => ReactNode
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

/** Khung bố cục 3 cột co giãn theo bề rộng màn hình, bọc TooltipProvider và Toaster. */
export function AppShell({
  cheDo,
  queueCollapsed,
  onToggleQueue,
  chatCollapsed,
  onToggleChat,
  hasCase,
  thoiGianMs,
  queueSlot,
  queueDrawerSlot,
  headerSlot,
  children,
  chatSlot,
  renderChat,
}: AppShellProps) {
  const isCompactChat = useMediaQuery('(max-width: 1279px)')
  const isCompactQueue = useMediaQuery('(max-width: 1023px)')

  const [drawerQueueOpen, setDrawerQueueOpen] = useState<boolean>(false)
  const [drawerChatOpen, setDrawerChatOpen] = useState<boolean>(false)

  const [prevCompactQueue, setPrevCompactQueue] = useState<boolean>(isCompactQueue)
  const [prevCompactChat, setPrevCompactChat] = useState<boolean>(isCompactChat)
  const [prevChatCollapsed, setPrevChatCollapsed] = useState<boolean>(chatCollapsed)

  if (prevCompactQueue !== isCompactQueue) {
    setPrevCompactQueue(isCompactQueue)
    if (drawerQueueOpen) {
      setDrawerQueueOpen(false)
    }
  }

  if (prevCompactChat !== isCompactChat) {
    setPrevCompactChat(isCompactChat)
    if (drawerChatOpen) {
      setDrawerChatOpen(false)
    }
  }

  if (prevChatCollapsed !== chatCollapsed) {
    setPrevChatCollapsed(chatCollapsed)
    if (isCompactChat && drawerChatOpen) {
      setDrawerChatOpen(false)
    }
  }

  const resolvedChat = renderChat
    ? hasCase
      ? renderChat(isCompactChat ? () => setDrawerChatOpen(false) : onToggleChat)
      : null
    : (chatSlot ?? null)
  const canShowChat = hasCase && resolvedChat !== null
  const queueOpen = isCompactQueue ? drawerQueueOpen : !queueCollapsed
  const chatOpen = isCompactChat ? drawerChatOpen && canShowChat : !chatCollapsed

  const handleToggleQueue = () => {
    if (isCompactQueue) {
      setDrawerQueueOpen((prev) => !prev)
      return
    }
    onToggleQueue()
  }

  const handleToggleChat = () => {
    if (isCompactChat) {
      if (!canShowChat) {
        return
      }
      setDrawerChatOpen((prev) => !prev)
      return
    }
    onToggleChat()
  }

  return (
    <TooltipProvider>
      <div className="h-screen w-full flex flex-col overflow-hidden bg-canvas text-fg">
        <TopBar
          cheDo={cheDo}
          queueOpen={queueOpen}
          onToggleQueue={handleToggleQueue}
          chatOpen={chatOpen}
          onToggleChat={handleToggleChat}
          chatAvailable={canShowChat}
        />

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {!isCompactQueue ? (
            <aside
              aria-label="Hàng đợi y lệnh"
              className={cn(
                'bg-surface border-r border-line shrink-0 overflow-hidden transition-[width] duration-180 ease-out',
                queueCollapsed ? 'w-[56px]' : 'w-[304px]',
              )}
            >
              {queueSlot}
            </aside>
          ) : null}

          <main
            aria-label="Nội dung thẩm định ca"
            className="flex-1 min-w-0 overflow-y-auto flex flex-col scroll-pt-20 overscroll-contain"
          >
            {headerSlot}

            <div className="w-full max-w-[920px] mx-auto px-5 py-3 flex-1 flex flex-col gap-3">
              {children}

              <footer className="mt-auto pt-4 border-t border-line flex items-center justify-between gap-4 flex-wrap text-xs text-fg-subtle">
                <span>Kết quả tham khảo. Dược sĩ kiểm chứng và quyết định.</span>
                {thoiGianMs != null ? (
                  <span className="tabular-nums">
                    Thời gian chạy: {thoiGianMs.toFixed(2).replace('.', ',')} ms
                  </span>
                ) : null}
              </footer>
            </div>
          </main>

          {!isCompactChat && !chatCollapsed && canShowChat ? (
            <aside
              aria-label="Hỏi thêm về ca này"
              className="w-[384px] bg-surface border-l border-line shrink-0 overflow-hidden flex flex-col"
            >
              {resolvedChat}
            </aside>
          ) : null}
        </div>

        <Dialog open={isCompactQueue && drawerQueueOpen} onOpenChange={setDrawerQueueOpen}>
          <DialogContent
            variant="drawer-left"
            tabIndex={-1}
            className="p-0"
            onOpenAutoFocus={(e) => {
              e.preventDefault()
              if (e.currentTarget instanceof HTMLElement) {
                e.currentTarget.focus()
              }
            }}
          >
            <DialogTitle className="sr-only">Hàng đợi y lệnh</DialogTitle>
            <DialogDescription className="sr-only">
              Danh sách các y lệnh chờ thẩm định
            </DialogDescription>
            <div
              className="relative flex h-full min-h-0 flex-col"
              onClick={(event) => {
                const target = event.target as HTMLElement | null
                if (target?.closest('[role="option"]')) {
                  setDrawerQueueOpen(false)
                }
              }}
            >
              <DialogClose asChild>
                <IconButton
                  icon={<X className="size-4" strokeWidth={1.75} />}
                  aria-label="Đóng hàng đợi"
                  className="absolute right-3 top-2.5 z-10"
                />
              </DialogClose>
              {queueDrawerSlot ?? queueSlot}
            </div>
          </DialogContent>
        </Dialog>

        <Dialog
          open={isCompactChat && drawerChatOpen && canShowChat}
          onOpenChange={setDrawerChatOpen}
        >
          <DialogContent
            variant="drawer-right"
            tabIndex={-1}
            className="p-0"
            onOpenAutoFocus={(e) => {
              e.preventDefault()
              if (e.currentTarget instanceof HTMLElement) {
                e.currentTarget.focus()
              }
            }}
          >
            <DialogTitle className="sr-only">Hỏi thêm về ca này</DialogTitle>
            <DialogDescription className="sr-only">
              Khung hỏi thêm có trích dẫn từ hồ sơ ca và nguồn thuốc
            </DialogDescription>
            <div className="flex h-full min-h-0 flex-col">{resolvedChat}</div>
          </DialogContent>
        </Dialog>

        <Toaster />
      </div>
    </TooltipProvider>
  )
}
