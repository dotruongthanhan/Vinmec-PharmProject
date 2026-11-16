import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Pill,
  Scale,
  Sparkles,
} from 'lucide-react'
import type { CheDo } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { IconButton } from '@/components/ui/icon-button'

export interface TopBarProps {
  cheDo: CheDo | null
  queueOpen: boolean
  onToggleQueue: () => void
  chatOpen: boolean
  onToggleChat: () => void
  chatAvailable?: boolean
}

/** Thanh tiêu đề trên cùng 48 px hiển thị tên công cụ, chế độ chạy và hai nút đóng mở thanh bên. */
export function TopBar({
  cheDo,
  queueOpen,
  onToggleQueue,
  chatOpen,
  onToggleChat,
  chatAvailable = true,
}: TopBarProps) {
  const isAiEnabled = Boolean(cheDo?.co_llm)

  return (
    <header
      className="h-12 bg-surface border-b border-line px-4 flex items-center justify-between gap-3 shrink-0"
      aria-label="Thanh điều hướng ứng dụng"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <IconButton
          icon={
            queueOpen ? (
              <PanelLeftClose className="size-4" strokeWidth={1.75} />
            ) : (
              <PanelLeftOpen className="size-4" strokeWidth={1.75} />
            )
          }
          aria-label={queueOpen ? 'Thu gọn hàng đợi y lệnh' : 'Mở hàng đợi y lệnh'}
          aria-expanded={queueOpen}
          onClick={onToggleQueue}
        />
        <Pill size={18} strokeWidth={1.75} className="text-primary shrink-0" aria-hidden="true" />
        <h1 className="text-md font-semibold text-fg truncate">Hỗ trợ thẩm định y lệnh</h1>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <Badge tone="warning" variant="soft">
          Dữ liệu giả lập
        </Badge>
        <Badge
          tone={isAiEnabled ? 'ai' : 'neutral'}
          variant="soft"
          icon={
            isAiEnabled ? (
              <Sparkles className="size-3.5" strokeWidth={1.75} />
            ) : (
              <Scale className="size-3.5" strokeWidth={1.75} />
            )
          }
        >
          {isAiEnabled ? 'AI bật' : 'Chỉ bộ luật'}
        </Badge>
        <IconButton
          icon={
            chatOpen ? (
              <PanelRightClose className="size-4" strokeWidth={1.75} />
            ) : (
              <PanelRightOpen className="size-4" strokeWidth={1.75} />
            )
          }
          aria-label={chatOpen ? 'Ẩn khung hỏi thêm' : 'Mở khung hỏi thêm'}
          aria-expanded={chatOpen}
          disabled={!chatAvailable}
          tooltip={
            !chatAvailable
              ? 'Chọn một ca để mở khung hỏi thêm'
              : chatOpen
                ? 'Ẩn khung hỏi thêm'
                : 'Mở khung hỏi thêm'
          }
          onClick={onToggleChat}
        />
      </div>
    </header>
  )
}
