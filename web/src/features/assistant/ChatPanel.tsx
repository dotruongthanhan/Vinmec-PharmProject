import {
  CornerDownRight,
  LoaderCircle,
  MessageSquareText,
  SendHorizontal,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { ChiSo, TrangThaiTraLoi, TrichDanTraLoi } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleChevron,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { EmptyState } from '@/components/ui/empty-state'
import { IconButton } from '@/components/ui/icon-button'
import { InlineAlert } from '@/components/ui/inline-alert'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  getChatStatusPresentation,
  inferMetricFromCitation,
  parseCitationsInText,
} from '@/lib/presentation'
import { ICON_OF_TONE } from '@/lib/severity'
import type { SemanticTone } from '@/lib/severity'
import type { EvidenceTarget } from '@/lib/uiTypes'
import type { ChatMessage } from '@/state/useChat'

export interface ChatPanelProps {
  caId: string
  cauHoiGoiY: readonly string[]
  messages: readonly ChatMessage[]
  sending: boolean
  hoiThemEnabled: boolean
  chiSo: readonly ChiSo[]
  onClose: () => void
  onSend: (caId: string, question: string) => Promise<void>
  onClear: (caId: string) => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

const CHAT_STATUS_TONE: Record<TrangThaiTraLoi, SemanticTone> = {
  ok: 'success',
  chua_san_sang: 'missing',
  khong_co_nguon: 'warning',
  ngoai_pham_vi: 'offlabel',
  loi: 'danger',
}

/** Thành phần D: Khung hỏi thêm về ca đang mở, có trích dẫn và kiểm chứng nguồn. */
export function ChatPanel({
  caId,
  cauHoiGoiY,
  messages,
  sending,
  hoiThemEnabled,
  chiSo,
  onClose,
  onSend,
  onClear,
  onOpenEvidence,
}: ChatPanelProps) {
  const [draft, setDraft] = useState<string>('')
  const [prevCaId, setPrevCaId] = useState<string>(caId)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  if (prevCaId !== caId) {
    setPrevCaId(caId)
    setDraft('')
  }

  useEffect(() => {
    const el = textareaRef.current
    if (!el) {
      return
    }
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`
  }, [draft])

  const openCitation = (td: TrichDanTraLoi, trigger: HTMLButtonElement) => {
    if (td.loai_ma === 'du_lieu' && td.ban_ghi_id) {
      onOpenEvidence(
        {
          kind: 'record',
          caId,
          banGhiId: td.ban_ghi_id,
          titleHint: td.nhan,
        },
        trigger,
      )
      return
    }
    if (td.loai_ma === 'tinh_toan') {
      const metric = inferMetricFromCitation(chiSo, td.ban_ghi_id, td.nhan)
      if (metric) {
        onOpenEvidence(
          {
            kind: 'metric',
            metric,
            titleHint: td.nhan,
          },
          trigger,
        )
        return
      }
    }
    onOpenEvidence(
      {
        kind: 'document',
        moTa: td.nhan,
        ghiChu:
          td.loai_ma === 'tai_lieu'
            ? 'Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức.'
            : null,
      },
      trigger,
    )
  }

  const handleSubmit = () => {
    if (!hoiThemEnabled || sending) {
      return
    }
    const clean = draft.trim()
    if (!clean) {
      return
    }
    setDraft('')
    void onSend(caId, clean)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key === 'Enter' &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      event.nativeEvent.keyCode !== 229
    ) {
      event.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex h-full w-full flex-col min-h-0" aria-label="Hỏi thêm về ca này">
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-line shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <MessageSquareText
            className="size-4 text-primary shrink-0"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          <h2 className="text-sm font-semibold text-fg truncate">Hỏi thêm về ca này</h2>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            disabled={messages.length === 0 || sending}
            onClick={() => onClear(caId)}
          >
            Xoá hội thoại
          </Button>
          <IconButton
            icon={<X className="size-4" strokeWidth={1.75} />}
            aria-label="Đóng khung hỏi thêm"
            onClick={onClose}
          />
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0" viewportClassName="p-4">
        <div className="flex flex-col gap-3">
          {!hoiThemEnabled ? (
            <InlineAlert tone="neutral" role="status">
              Chức năng hỏi thêm chưa sẵn sàng
            </InlineAlert>
          ) : null}

          {!hoiThemEnabled && messages.length === 0 && cauHoiGoiY.length > 0 ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-fg-subtle">
                Câu hỏi gợi ý cho ca {caId}:
              </p>
              {cauHoiGoiY.map((q) => (
                <Button
                  key={q}
                  variant="secondary"
                  size="sm"
                  disabled
                  iconLeft={<CornerDownRight className="size-3.5" strokeWidth={1.75} />}
                  className="h-auto min-h-8 justify-start whitespace-normal py-1.5 text-left font-normal text-fg-subtle"
                >
                  {q}
                </Button>
              ))}
            </div>
          ) : null}

          {hoiThemEnabled && messages.length === 0 && !sending ? (
            <div className="flex flex-col gap-3">
              <EmptyState
                icon={MessageSquareText}
                title="Hỏi thêm về ca đang mở"
                description="Chọn gợi ý hoặc nhập câu hỏi có trích dẫn từ hồ sơ và nguồn thuốc."
                className="px-2 py-4"
              />
              {cauHoiGoiY.length > 0 ? (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-medium text-fg-muted">
                    Câu hỏi gợi ý cho ca {caId}:
                  </p>
                  {cauHoiGoiY.map((q) => (
                    <Button
                      key={q}
                      variant="soft"
                      size="sm"
                      iconLeft={<CornerDownRight className="size-3.5" strokeWidth={1.75} />}
                      className="h-auto min-h-8 justify-start whitespace-normal py-1.5 text-left font-normal"
                      onClick={() => {
                        void onSend(caId, q)
                      }}
                    >
                      {q}
                    </Button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {messages.length > 0 ? (
            <div className="flex flex-col gap-3">
              {messages.map((msg) => {
                if (msg.vai === 'nguoi_dung') {
                  return (
                    <div
                      key={msg.id}
                      className="self-end max-w-[90%] bg-primary-soft border border-primary-line/60 text-fg rounded-md px-3 py-2 text-sm whitespace-pre-wrap break-words"
                    >
                      {msg.noi_dung}
                    </div>
                  )
                }

                const statusInfo = getChatStatusPresentation(msg.tra_loi.trang_thai)
                const statusTone = CHAT_STATUS_TONE[msg.tra_loi.trang_thai] ?? 'neutral'
                const StatusIcon = ICON_OF_TONE[statusTone]
                const segments = parseCitationsInText(
                  msg.tra_loi.noi_dung,
                  msg.tra_loi.trich_dan,
                )

                return (
                  <div
                    key={msg.id}
                    className="self-stretch bg-surface border border-line rounded-md p-3 text-sm flex flex-col gap-2.5"
                  >
                    <div className="flex items-center">
                      <Badge
                        tone={statusTone}
                        variant="soft"
                        icon={<StatusIcon className="size-3.5" strokeWidth={1.75} />}
                      >
                        {statusInfo.label}
                      </Badge>
                    </div>

                    <div className="text-sm text-fg whitespace-pre-wrap break-words leading-relaxed">
                      {segments.map((seg, idx) =>
                        seg.kind === 'text' ? (
                          <span key={`${msg.id}-t-${idx}`}>{seg.value}</span>
                        ) : (
                          <button
                            key={`${msg.id}-c-${idx}`}
                            type="button"
                            onClick={(e) => openCitation(seg.citation, e.currentTarget)}
                            title={seg.citation.nhan}
                            aria-label={`Mở trích dẫn ${seg.label}: ${seg.citation.nhan}`}
                            className="inline-flex min-h-6 min-w-6 items-center justify-center py-0.5 align-baseline mx-0.5 cursor-pointer rounded-full"
                          >
                            <Badge
                              tone="ai"
                              variant="soft"
                              className="h-[18px] min-h-0 px-1.5 py-0 text-2xs font-semibold tabular-nums hover:bg-primary-soft hover:border-primary-line hover:text-primary"
                            >
                              {seg.label}
                            </Badge>
                          </button>
                        ),
                      )}
                    </div>

                    {msg.tra_loi.trich_dan.length > 0 ? (
                      <div className="flex flex-col gap-1.5 border-t border-line pt-2">
                        <span className="text-xs font-medium text-fg-subtle">Trích dẫn:</span>
                        <div className="flex flex-col gap-1">
                          {msg.tra_loi.trich_dan.map((td) => (
                            <button
                              key={`${msg.id}-ref-${td.so}`}
                              type="button"
                              onClick={(e) => openCitation(td, e.currentTarget)}
                              className="flex w-full cursor-pointer items-start gap-2 rounded-sm border border-line bg-surface-hover px-2.5 py-1.5 text-left text-xs text-fg transition-colors duration-120 hover:border-primary-line hover:bg-primary-soft/50"
                            >
                              <Badge
                                tone="neutral"
                                variant="outline"
                                className="h-[18px] shrink-0 px-1.5 text-2xs tabular-nums"
                              >
                                {td.so}
                              </Badge>
                              <span className="min-w-0 flex-1 break-words">
                                <span className="font-medium text-primary">{td.nhan}</span>
                                {td.ban_ghi_id ? (
                                  <span className="ml-1.5 font-mono text-2xs text-fg-subtle">
                                    ({td.ban_ghi_id})
                                  </span>
                                ) : null}
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {msg.tra_loi.cong_cu_da_goi.length > 0 ? (
                      <Collapsible className="border-t border-line pt-2">
                        <CollapsibleTrigger className="group inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-fg-muted hover:text-fg">
                          <CollapsibleChevron size={14} />
                          <span>Hệ thống đã tra gì ({msg.tra_loi.cong_cu_da_goi.length})</span>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="mt-1.5 pl-4">
                          <ul className="list-disc space-y-1 text-xs text-fg-muted">
                            {msg.tra_loi.cong_cu_da_goi.map((tool, tIdx) => (
                              <li
                                key={`${msg.id}-tool-${tIdx}`}
                                className="whitespace-pre-wrap break-words"
                              >
                                {tool}
                              </li>
                            ))}
                          </ul>
                        </CollapsibleContent>
                      </Collapsible>
                    ) : null}
                  </div>
                )
              })}
            </div>
          ) : null}

          {sending ? (
            <InlineAlert
              tone="ai"
              role="status"
              ariaLive="polite"
              icon={<LoaderCircle className="size-4 animate-spin" strokeWidth={1.75} />}
            >
              Đang xử lý câu hỏi…
            </InlineAlert>
          ) : null}
        </div>
      </ScrollArea>

      <div className="border-t border-line bg-surface px-4 py-3 flex flex-col gap-1.5 shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            rows={1}
            aria-label="Nhập câu hỏi về ca đang mở"
            placeholder={
              hoiThemEnabled
                ? 'Nhập câu hỏi về ca đang mở… (Enter gửi, Shift+Enter xuống dòng)'
                : 'Chức năng hỏi thêm chưa sẵn sàng'
            }
            value={draft}
            disabled={!hoiThemEnabled || sending}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 min-h-[38px] max-h-[132px] resize-none overflow-y-auto rounded-sm border border-line-strong bg-surface px-2.5 py-2 text-sm text-fg placeholder:text-fg-subtle disabled:bg-surface-muted disabled:text-fg-disabled disabled:cursor-not-allowed"
          />
          <IconButton
            variant="primary"
            size="md"
            icon={<SendHorizontal className="size-4" strokeWidth={1.75} />}
            aria-label="Gửi câu hỏi"
            disabled={!hoiThemEnabled || !draft.trim() || sending}
            onClick={handleSubmit}
          />
        </div>
        <p className="text-2xs text-fg-subtle">
          Trả lời tham khảo, có trích dẫn. Không dán dữ liệu người bệnh thật.
        </p>
      </div>
    </div>
  )
}
