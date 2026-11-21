import {
  CornerDownRight,
  ExternalLink,
  History,
  LoaderCircle,
  MessageSquareText,
  MessagesSquare,
  PanelRightClose,
  RotateCw,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  Square,
  X,
} from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { ReviewApiClient } from '@/api/client'
import type {
  BuocAI,
  ChiTietCa,
  DoanNguon,
  NhanDinh,
  TrangThaiBuocAI,
  TrangThaiTraLoi,
  TrichDanTraLoi,
} from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ClinicalMarkdown } from '@/components/ui/ClinicalMarkdown'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AiStepList, toStepStatusMap } from '@/features/findings/AiStepList'
import { cn } from '@/lib/cn'
import {
  formatAiElapsedClock,
  pickStepStatusAnnouncement,
  splitHighlightSegments,
} from '@/lib/aiReview'
import { buildSourceLink } from '@/lib/sourceLink'
import {
  MAX_ASSISTANT_QUESTION_LENGTH,
  buildSuggestedQuestions,
  getAssistantInputState,
} from '@/lib/assistant'
import { extractOrderCode } from '@/lib/displayFormat'
import { inferMetricFromCitation } from '@/lib/presentation'
import type { EvidenceTarget } from '@/lib/uiTypes'
import { formatHistoryTime } from '@/lib/historyTime'
import { HistoryDialog } from './HistoryDialog'
import type { AssistantHistoryEntry } from './HistoryDialog'
import { GLOBAL_CHAT_ID } from '@/state/useChat'
import type { AskProgressSnapshot, ChatMessage } from '@/state/useChat'

const EMPTY_ASK_PROGRESS: AskProgressSnapshot = {
  cacBuoc: [],
  daChayMs: null,
}

const GLOBAL_SUGGESTED_QUESTIONS: readonly string[] = [
  'Tóm tắt các y lệnh có cảnh báo nghiêm trọng cần ưu tiên',
  'Những ca nào trong danh sách cần chú ý chức năng thận hoặc dị ứng?',
  'Tra cứu liều Meropenem theo mức CrCl trong suy thận',
]

export interface FocusedFindingContext {
  nhanDinhId: string
  label: string
}

export interface AssistantPanelProps {
  client: ReviewApiClient
  detail: ChiTietCa | null
  globalHoiThemEnabled?: boolean
  history: readonly AssistantHistoryEntry[]
  onOpenHistory: (chatId: string) => void
  attentionFindings: readonly NhanDinh[]
  messages: readonly ChatMessage[]
  sending: boolean
  askProgress?: AskProgressSnapshot
  lastStatus: TrangThaiTraLoi | null
  focusedFinding: FocusedFindingContext | null
  onClearFocusedFinding: () => void
  onSend: (caId: string, question: string, nhanDinhId?: string | null) => Promise<void>
  onStop: (caId: string) => void
  onRetryLast: (caId: string) => Promise<void>
  onClear: (caId: string) => void
  onClose: () => void
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

/** Khối tiến trình hỏi đáp thu gọn hiển thị trong lúc đang gửi câu hỏi. */
export function AssistantLiveProgress({
  steps,
  daChayMs = null,
}: {
  steps: readonly BuocAI[]
  daChayMs?: number | null
}) {
  const runningStep = steps.find((step) => step.trang_thai === 'dang_chay')
  const anchorKey = `${daChayMs ?? 'null'}:${runningStep ? `${runningStep.ma}:${runningStep.thoi_gian_ms ?? 'null'}` : 'none'}`

  const [tickState, setTickState] = useState<{ key: string; deltaMs: number }>({
    key: anchorKey,
    deltaMs: 0,
  })
  const effectiveDeltaMs = tickState.key === anchorKey ? tickState.deltaMs : 0

  useEffect(() => {
    const anchor = Date.now()
    const timer = setInterval(() => {
      setTickState({
        key: anchorKey,
        deltaMs: Math.max(0, Date.now() - anchor),
      })
    }, 500)
    return () => {
      clearInterval(timer)
    }
  }, [anchorKey])

  const statusSignature = steps.map((s) => `${s.ma}:${s.trang_thai}`).join('|')
  const [prevStatusSignature, setPrevStatusSignature] = useState<string>(statusSignature)
  const [prevStepMap, setPrevStepMap] = useState<Record<string, TrangThaiBuocAI>>(() =>
    toStepStatusMap(steps),
  )
  const [liveAnnouncement, setLiveAnnouncement] = useState<string>(() =>
    pickStepStatusAnnouncement(steps, null),
  )

  if (statusSignature !== prevStatusSignature) {
    const nextMap = toStepStatusMap(steps)
    const nextMessage = pickStepStatusAnnouncement(steps, prevStepMap)
    setPrevStatusSignature(statusSignature)
    setPrevStepMap(nextMap)
    if (nextMessage) {
      setLiveAnnouncement(nextMessage)
    }
  }

  return (
    <div className="rounded-md border border-ai-line bg-ai-bg px-3 py-2.5 text-sm text-ai-fg">
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {liveAnnouncement}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <div className="flex min-w-0 items-center gap-2">
          <Sparkles className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          <span className="font-medium break-words">Đang tra cứu dữ liệu và nguồn</span>
        </div>

        <span
          aria-hidden="true"
          className="shrink-0 text-xs text-ai-fg/80 tabular-nums"
        >
          {formatAiElapsedClock((daChayMs ?? 0) + effectiveDeltaMs)}
        </span>
      </div>

      <div className="mt-2.5">
        <AiStepList steps={steps} liveDeltaMs={effectiveDeltaMs} />
      </div>
    </div>
  )
}

/** Nút thu gọn / mở rộng danh sách bước gắn dưới tin nhắn trả lời trong phiên. */
export function AssistantMessageSteps({
  steps,
  defaultExpanded = false,
}: {
  steps: readonly BuocAI[]
  defaultExpanded?: boolean
}) {
  const stepsRegionId = useId()
  const [expanded, setExpanded] = useState<boolean>(defaultExpanded)

  if (steps.length === 0) {
    return null
  }

  return (
    <div className="min-w-0">
      <Button
        variant="ghost"
        size="sm"
        aria-expanded={expanded}
        aria-controls={stepsRegionId}
        onClick={() => setExpanded((prev) => !prev)}
        className="px-2 text-xs text-fg-subtle hover:text-fg"
      >
        {expanded ? 'Ẩn các bước' : `Xem các bước (${steps.length})`}
      </Button>

      <div
        id={stepsRegionId}
        hidden={!expanded}
        className={
          expanded
            ? 'mt-1.5 rounded-md border border-line bg-surface-muted/40 px-3 py-2.5'
            : undefined
        }
      >
        {expanded ? <AiStepList steps={steps} liveDeltaMs={0} /> : null}
      </div>
    </div>
  )
}

type AssistantTab = 'hoi_dap' | 'lich_su' | 'nguon'

interface SourceSelection {
  caId: string
  doanTrichId: string
  nhan: string
  trichNguyenVan: string
}

type SourceLoadState =
  | { key: string; status: 'loading' }
  | { key: string; status: 'error'; message: string }
  | { key: string; status: 'loaded'; data: DoanNguon }

/** Khung Trợ lý AI cột phải: gồm thẻ Hỏi đáp và thẻ Nguồn, hỗ trợ trích dẫn và AbortController. */
export function AssistantPanel({
  client,
  detail,
  globalHoiThemEnabled = true,
  history,
  onOpenHistory,
  attentionFindings,
  messages,
  sending,
  askProgress = EMPTY_ASK_PROGRESS,
  lastStatus,
  focusedFinding,
  onClearFocusedFinding,
  onSend,
  onStop,
  onRetryLast,
  onClear,
  onClose,
  onOpenEvidence,
}: AssistantPanelProps) {
  const [activeTab, setActiveTab] = useState<AssistantTab>('hoi_dap')
  const [historyOpenId, setHistoryOpenId] = useState<string | null>(null)
  const [draft, setDraft] = useState<string>('')
  const [sourceSelection, setSourceSelection] = useState<SourceSelection | null>(null)
  const [sourceState, setSourceState] = useState<SourceLoadState | null>(null)
  const [sourceReloadTick, setSourceReloadTick] = useState<number>(0)

  const activeChatId = detail?.ca_id ?? GLOBAL_CHAT_ID
  const [prevCaId, setPrevCaId] = useState<string>(activeChatId)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  if (prevCaId !== activeChatId) {
    setPrevCaId(activeChatId)
    setDraft('')
    setSourceSelection(null)
    setSourceState(null)
    setActiveTab('hoi_dap')
  }

  useEffect(() => {
    const el = textareaRef.current
    if (!el) {
      return
    }
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`
  }, [draft])

  const sourceFetchKey = sourceSelection
    ? `${sourceSelection.caId}::${sourceSelection.doanTrichId}::${sourceReloadTick}`
    : null

  useEffect(() => {
    if (!sourceSelection || !sourceFetchKey) {
      return
    }
    let cancelled = false
    client
      .getSource(sourceSelection.caId, sourceSelection.doanTrichId)
      .then((data) => {
        if (cancelled) {
          return
        }
        setSourceState({ key: sourceFetchKey, status: 'loaded', data })
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        const message =
          err instanceof Error && err.message
            ? err.message
            : 'Không tải được đoạn nguồn tài liệu.'
        setSourceState({ key: sourceFetchKey, status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [client, sourceSelection, sourceFetchKey])

  const hoiThemEnabled = detail ? Boolean(detail.che_do.hoi_them) : Boolean(globalHoiThemEnabled)
  const inputState = getAssistantInputState({
    hasCase: true,
    hoiThemEnabled,
    lastStatus,
    sending,
    draft,
  })

  const suggestedQuestions = useMemo(
    () => (detail ? buildSuggestedQuestions(detail, attentionFindings) : GLOBAL_SUGGESTED_QUESTIONS),
    [detail, attentionFindings],
  )

  const orderCode = detail
    ? extractOrderCode(detail.chi_tiet.y_lenh.thong_tin_text, detail.ca_id)
    : null

  const handleOpenCitation = (td: TrichDanTraLoi, trigger: HTMLButtonElement) => {
    if (td.loai_ma === 'tai_lieu' && td.doan_trich_id) {
      setSourceSelection({
        caId: activeChatId,
        doanTrichId: td.doan_trich_id,
        nhan: td.nhan,
        trichNguyenVan: td.trich_nguyen_van ?? '',
      })
      setActiveTab('nguon')
      return
    }
    if (!detail) {
      if (td.trich_nguyen_van || td.doan_trich_id) {
        setSourceSelection({
          caId: activeChatId,
          doanTrichId: td.doan_trich_id ?? td.ban_ghi_id ?? `ref-${td.so}`,
          nhan: td.nhan,
          trichNguyenVan: td.trich_nguyen_van ?? '',
        })
        setActiveTab('nguon')
      } else {
        onOpenEvidence(
          {
            kind: 'document',
            moTa: td.nhan,
            ghiChu: `Căn cứ tham chiếu [${td.so}]: ${td.nhan}`,
          },
          trigger,
        )
      }
      return
    }
    if (td.loai_ma === 'du_lieu' && td.ban_ghi_id) {
      onOpenEvidence(
        {
          kind: 'record',
          caId: detail.ca_id,
          banGhiId: td.ban_ghi_id,
          titleHint: td.nhan,
        },
        trigger,
      )
      return
    }
    if (td.loai_ma === 'tinh_toan') {
      const metric = inferMetricFromCitation(detail.chi_so, td.ban_ghi_id, td.nhan)
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
            ? 'Không có mã đoạn nguồn để mở trực tiếp.'
            : null,
      },
      trigger,
    )
  }

  const handleSubmit = () => {
    if (!inputState.canSend) {
      return
    }
    const clean = draft.trim()
    const targetFindingId = detail ? (focusedFinding?.nhanDinhId ?? null) : null
    setDraft('')
    onClearFocusedFinding()
    void onSend(activeChatId, clean, targetFindingId)
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

  const handlePickSuggestion = (question: string) => {
    setDraft(question)
    textareaRef.current?.focus()
  }

  const currentSourceLoaded =
    sourceFetchKey && sourceState?.key === sourceFetchKey && sourceState.status === 'loaded'
      ? sourceState.data
      : null
  const currentSourceError =
    sourceFetchKey && sourceState?.key === sourceFetchKey && sourceState.status === 'error'
      ? sourceState.message
      : null
  const currentSourceLoading =
    Boolean(sourceFetchKey) &&
    (!sourceState || sourceState.key !== sourceFetchKey || sourceState.status === 'loading')
  const safeSourceUrl = currentSourceLoaded
    ? buildSourceLink({
        urlGoc: currentSourceLoaded.url_goc,
        duongDanMuc: currentSourceLoaded.duong_dan_muc,
        trichNguyenVan: sourceSelection?.trichNguyenVan,
      })
    : null

  return (
    <div className="flex h-full w-full flex-col min-h-0 bg-surface" aria-label="Trợ lý AI">
      <Tabs
        value={activeTab}
        onValueChange={(val) => setActiveTab(val as AssistantTab)}
        className="flex h-full min-h-0 flex-col"
      >
        <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-line px-4">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="text-sm font-semibold text-fg">Trợ lý</h2>
            <TabsList aria-label="Chế độ khung trợ lý" className="border-b-0 px-0 gap-4">
              <TabsTrigger value="hoi_dap" className="py-3 text-xs">
                Hỏi đáp
              </TabsTrigger>
              <TabsTrigger value="lich_su" className="py-3 text-xs">
                Lịch sử
              </TabsTrigger>
              <TabsTrigger value="nguon" className="py-3 text-xs">
                Nguồn
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {activeTab === 'hoi_dap' && messages.length > 0 ? (
              <Button
                variant="ghost"
                size="sm"
                disabled={sending}
                onClick={() => onClear(activeChatId)}
              >
                Xoá
              </Button>
            ) : null}
            <IconButton
              icon={<PanelRightClose className="size-4" strokeWidth={1.75} />}
              aria-label="Thu gọn trợ lý"
              onClick={onClose}
            />
          </div>
        </div>

        {/* Thẻ Hỏi đáp */}
        <TabsContent
          value="hoi_dap"
          className="hidden data-[state=active]:flex flex-1 min-h-0 flex-col"
        >
          <ScrollArea className="flex-1 min-h-0" viewportClassName="p-4">
            <div className="flex flex-col gap-3">
              <>
                {inputState.lockMessage ? (
                  <InlineAlert tone="neutral" role="status">
                    {inputState.lockMessage}
                  </InlineAlert>
                ) : null}

                {!inputState.lockMessage && messages.length === 0 && !sending ? (
                  <div className="flex flex-col gap-3">
                    {detail ? (
                      <p className="text-sm text-fg-muted leading-relaxed">
                        Đặt câu hỏi về dữ liệu ca, liều dùng hoặc nguồn thuốc của{' '}
                        <span className="font-mono font-medium text-fg">{orderCode}</span>.
                      </p>
                    ) : (
                      <p className="text-sm text-fg-muted leading-relaxed">
                        Hỏi đáp chung về danh sách y lệnh đang chờ hoặc tra cứu thông tin thuốc trong kho.
                      </p>
                    )}

                    {suggestedQuestions.length > 0 ? (
                      <div className="flex flex-col gap-1.5">
                        <span className="text-xs font-medium text-fg-subtle">
                          Gợi ý câu hỏi
                        </span>
                        {suggestedQuestions.map((q) => (
                          <Button
                            key={q}
                            variant="secondary"
                            size="sm"
                            iconLeft={<CornerDownRight className="size-3.5" strokeWidth={1.75} />}
                            className="h-auto min-h-8 justify-start whitespace-normal py-1.5 text-left font-normal"
                            onClick={() => handlePickSuggestion(q)}
                          >
                            {q}
                          </Button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                  {messages.length > 0 ? (
                    <div className="flex flex-col gap-4">
                      {messages.map((msg) => {
                        if (msg.vai === 'nguoi_dung') {
                          return (
                            <div
                              key={msg.id}
                              className="self-end max-w-[88%] rounded-md border border-line bg-surface-muted px-3 py-2 text-sm text-fg whitespace-pre-wrap break-words"
                            >
                              {msg.noi_dung}
                            </div>
                          )
                        }

                        const status = msg.tra_loi.trang_thai
                        const msgSteps = msg.cac_buoc ?? []
                        const errorSteps = msgSteps.filter(
                          (step) => step.trang_thai === 'loi' && (step.ly_do || step.goi_y),
                        )

                        return (
                          <div
                            key={msg.id}
                            className="flex flex-col gap-2.5 border-b border-line pb-3.5 last:border-b-0 last:pb-0 text-sm text-fg"
                          >
                            {/* Quá trình xử lý nằm trên câu trả lời (giữa tin nhắn người dùng và tin nhắn AI), thu gọn sẵn. */}
                            {msgSteps.length > 0 ? (
                              <AssistantMessageSteps steps={msgSteps} />
                            ) : null}

                            {status === 'khong_co_nguon' ? (
                              <div>
                                <Badge tone="neutral" variant="outline">
                                  Không có nguồn phù hợp
                                </Badge>
                              </div>
                            ) : status === 'ngoai_pham_vi' ? (
                              <div>
                                <Badge tone="neutral" variant="outline">
                                  Ngoài phạm vi
                                </Badge>
                              </div>
                            ) : status === 'loi' ? (
                              <div>
                                <Badge tone="danger" variant="soft">
                                  Không hoàn tất
                                </Badge>
                              </div>
                            ) : status === 'chua_san_sang' ? (
                              <div>
                                <Badge tone="neutral" variant="soft">
                                  Chưa sẵn sàng
                                </Badge>
                              </div>
                            ) : null}

                            <ClinicalMarkdown
                              text={msg.tra_loi.noi_dung}
                              citations={msg.tra_loi.trich_dan}
                              onCitationClick={handleOpenCitation}
                            />

                            {errorSteps.length > 0 ? (
                              <div
                                role="alert"
                                className="flex flex-col gap-1.5 rounded-sm border border-warning-line bg-warning-bg px-2.5 py-2 text-xs text-warning-fg"
                              >
                                {errorSteps.map((step, errIdx) => (
                                  <div
                                    key={`${msg.id}-err-${step.ma || errIdx}`}
                                    className="flex flex-col gap-0.5"
                                  >
                                    {step.ly_do ? (
                                      <p className="font-medium whitespace-pre-wrap break-words">
                                        {step.ly_do}
                                      </p>
                                    ) : null}
                                    {step.goi_y ? (
                                      <p className="text-fg-muted whitespace-pre-wrap break-words">
                                        {step.goi_y}
                                      </p>
                                    ) : null}
                                  </div>
                                ))}
                              </div>
                            ) : null}

                            {status === 'loi' ? (
                              <div>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  iconLeft={<RotateCw className="size-3.5" strokeWidth={1.75} />}
                                  onClick={() => {
                                    void onRetryLast(activeChatId)
                                  }}
                                >
                                  Gửi lại
                                </Button>
                              </div>
                            ) : null}

                            {msg.tra_loi.trich_dan.length > 0 ? (
                              <Collapsible className="border-t border-line pt-2">
                                <CollapsibleTrigger className="group inline-flex cursor-pointer items-center gap-1 text-xs text-fg-subtle hover:text-fg">
                                  <CollapsibleChevron size={13} />
                                  <span>Nguồn tham khảo ({msg.tra_loi.trich_dan.length})</span>
                                </CollapsibleTrigger>
                                <CollapsibleContent className="mt-1.5">
                                  <ol className="flex flex-col gap-1.5">
                                    {msg.tra_loi.trich_dan.map((td) => (
                                      <li key={`${msg.id}-ref-${td.so}`}>
                                        <button
                                          type="button"
                                          onClick={(e) => handleOpenCitation(td, e.currentTarget)}
                                          className="flex w-full cursor-pointer items-start gap-2 rounded-sm px-1.5 py-1 text-left text-xs text-fg-muted transition-colors duration-120 hover:bg-surface-hover hover:text-fg"
                                        >
                                          <span className="font-mono text-2xs font-semibold text-primary tabular-nums shrink-0 mt-0.5">
                                            [{td.so}]
                                          </span>
                                          <span className="min-w-0 flex-1 break-words">
                                            <span className="font-medium text-fg">{td.nhan}</span>
                                            {td.ban_ghi_id ? (
                                              <span className="ml-1.5 font-mono text-2xs text-fg-subtle">
                                                {td.ban_ghi_id}
                                              </span>
                                            ) : null}
                                          </span>
                                        </button>
                                      </li>
                                    ))}
                                  </ol>
                                </CollapsibleContent>
                              </Collapsible>
                            ) : null}

                            {msg.tra_loi.cong_cu_da_goi.length > 0 ? (
                              <Collapsible className="pt-1">
                                <CollapsibleTrigger className="group inline-flex cursor-pointer items-center gap-1 text-xs text-fg-subtle hover:text-fg">
                                  <CollapsibleChevron size={13} />
                                  <span>Đã tra ({msg.tra_loi.cong_cu_da_goi.length})</span>
                                </CollapsibleTrigger>
                                <CollapsibleContent className="mt-1 pl-4">
                                  <ul className="list-disc space-y-0.5 text-xs text-fg-subtle">
                                    {msg.tra_loi.cong_cu_da_goi.map((tool, tIdx) => (
                                      <li key={`${msg.id}-tool-${tIdx}`} className="font-mono">
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
                    askProgress.cacBuoc.length > 0 ? (
                      <AssistantLiveProgress
                        key={activeChatId}
                        steps={askProgress.cacBuoc}
                        daChayMs={askProgress.daChayMs}
                      />
                    ) : (
                      <div
                        className="flex items-center gap-2 py-2 text-xs text-fg-muted"
                        role="status"
                        aria-live="polite"
                      >
                        <LoaderCircle
                          className="size-3.5 motion-safe:animate-spin text-primary shrink-0"
                          strokeWidth={1.75}
                          aria-hidden="true"
                        />
                        <span>Đang tra cứu dữ liệu và nguồn…</span>
                      </div>
                    )
                  ) : null}
              </>
            </div>
          </ScrollArea>

          {/* Vùng nhập câu hỏi — phong cách khung nhập liền khối như Claude Code */}
          <div className="shrink-0 border-t border-line bg-surface px-4 py-3 flex flex-col gap-2">
            {detail ? (
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="text-fg-subtle">
                  Ca đang mở:{' '}
                  <span className="font-mono font-medium text-fg">{orderCode}</span>
                </span>
                {focusedFinding ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-primary-line bg-primary-soft px-2 py-0.5 text-2xs font-medium text-primary">
                    <span className="max-w-44 truncate">{focusedFinding.label}</span>
                    <button
                      type="button"
                      aria-label="Bỏ chọn nhận định đang hỏi"
                      onClick={onClearFocusedFinding}
                      className="inline-flex cursor-pointer items-center justify-center rounded-full hover:bg-primary/15"
                    >
                      <X className="size-3" strokeWidth={1.75} aria-hidden="true" />
                    </button>
                  </span>
                ) : null}
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-xs text-fg-subtle">
                <span>Chế độ: Hỏi đáp chung (toàn bộ danh sách y lệnh)</span>
              </div>
            )}

            <div className="flex flex-col gap-1.5 rounded-md border border-line-strong bg-surface-muted/40 p-2 focus-within:border-primary focus-within:bg-surface transition-colors duration-120">
              <textarea
                ref={textareaRef}
                rows={1}
                maxLength={MAX_ASSISTANT_QUESTION_LENGTH}
                aria-label="Nhập câu hỏi về ca đang mở"
                placeholder={
                  inputState.lockMessage
                    ? inputState.lockMessage
                    : 'Nhập câu hỏi… (Enter gửi, Shift+Enter xuống dòng)'
                }
                value={draft}
                disabled={inputState.inputLocked}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full min-h-[28px] max-h-[132px] resize-none overflow-y-auto border-0 bg-transparent px-1 py-0.5 text-sm text-fg placeholder:text-fg-subtle focus-visible:outline-none disabled:cursor-not-allowed disabled:text-fg-disabled"
              />

              <div className="flex items-center justify-between gap-2 pt-0.5">
                <span className="text-2xs text-fg-subtle">
                  {inputState.showCharCounter ? (
                    <span className="font-mono tabular-nums">
                      Còn {inputState.remainingChars}
                    </span>
                  ) : (
                    'Dược sĩ kiểm chứng và quyết định'
                  )}
                </span>

                {inputState.showStop ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    iconLeft={<Square className="size-3" strokeWidth={1.75} />}
                    onClick={() => onStop(activeChatId)}
                    className="h-7 shrink-0"
                  >
                    Dừng
                  </Button>
                ) : (
                  <IconButton
                    variant="primary"
                    size="sm"
                    icon={<SendHorizontal className="size-3.5" strokeWidth={1.75} />}
                    aria-label="Gửi câu hỏi"
                    disabled={!inputState.canSend}
                    onClick={handleSubmit}
                    className="h-7 w-7 shrink-0 rounded-sm"
                  />
                )}
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Thẻ Lịch sử: dòng gọn nhận diện y lệnh và người bệnh, bấm để mở hộp thoại chi tiết */}
        <TabsContent
          value="lich_su"
          className="hidden data-[state=active]:flex flex-1 min-h-0 flex-col"
        >
          <ScrollArea className="flex-1 min-h-0" viewportClassName="p-2">
            {history.length === 0 ? (
              <EmptyState
                icon={History}
                title="Chưa có hội thoại"
                description="Các y lệnh bạn đã hỏi trợ lý sẽ hiện ở đây để mở lại nhanh."
                className="px-2 py-8"
              />
            ) : (
              <ul className="flex flex-col" aria-label="Hội thoại gần đây">
                {history.map((entry) => {
                  const isGlobalEntry = entry.chatId === GLOBAL_CHAT_ID
                  const timeText = formatHistoryTime(entry.lastAt)
                  return (
                    <li key={entry.chatId}>
                      <button
                        type="button"
                        onClick={() => setHistoryOpenId(entry.chatId)}
                        className="flex w-full cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-left transition-colors duration-120 hover:bg-surface-hover"
                      >
                        {isGlobalEntry ? (
                          <MessagesSquare className="size-3.5 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                        ) : (
                          <MessageSquareText className="size-3.5 shrink-0 text-fg-muted" strokeWidth={1.75} aria-hidden="true" />
                        )}
                        <span className="min-w-0 flex-1">
                          <span className={cn('block truncate text-xs font-semibold text-fg', !isGlobalEntry && 'font-mono')}>
                            {entry.title}
                          </span>
                          {entry.patient ? (
                            <span className="block truncate text-2xs text-fg-muted">{entry.patient}</span>
                          ) : null}
                        </span>
                        {timeText ? (
                          <span className="shrink-0 text-2xs text-fg-subtle tabular-nums">{timeText}</span>
                        ) : null}
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </ScrollArea>
          <HistoryDialog
            entry={history.find((entry) => entry.chatId === historyOpenId) ?? null}
            onOpenChange={(open) => {
              if (!open) {
                setHistoryOpenId(null)
              }
            }}
            onGoTo={(chatId) => {
              setActiveTab('hoi_dap')
              onOpenHistory(chatId)
            }}
          />
        </TabsContent>
        {/* Thẻ Nguồn */}
        <TabsContent
          value="nguon"
          className="hidden data-[state=active]:flex flex-1 min-h-0 flex-col"
        >
          <ScrollArea className="flex-1 min-h-0" viewportClassName="p-4">
            {!sourceSelection ? (
              <EmptyState
                icon={ShieldCheck}
                title="Chưa chọn đoạn nguồn"
                description="Bấm một trích dẫn tài liệu [n] trong phần Hỏi đáp để xem nguyên văn đoạn nguồn tại đây."
                className="px-2 py-8"
              />
            ) : currentSourceLoading ? (
              <div className="flex flex-col gap-3" role="status" aria-label="Đang tải đoạn nguồn">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-32 w-full" />
              </div>
            ) : currentSourceError ? (
              <InlineAlert
                tone="danger"
                role="alert"
                title="Không tải được đoạn nguồn"
                action={
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setSourceReloadTick((n) => n + 1)}
                  >
                    Thử lại
                  </Button>
                }
              >
                {currentSourceError}
              </InlineAlert>
            ) : currentSourceLoaded ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-fg">
                      {currentSourceLoaded.nguon_nhan}
                    </h3>
                    <p className="mt-0.5 text-xs text-fg-muted">
                      {currentSourceLoaded.duong_dan_muc}
                    </p>
                  </div>
                  <Badge
                    tone={currentSourceLoaded.tang_tin_cay === 1 ? 'success' : 'neutral'}
                    variant="soft"
                    className="shrink-0 tabular-nums"
                  >
                    Tầng {currentSourceLoaded.tang_tin_cay}
                  </Badge>
                </div>

                <div className="text-xs text-fg-subtle">
                  Phiên bản: {currentSourceLoaded.phien_ban}
                </div>

                {safeSourceUrl ? (
                  <div>
                    <a
                      href={safeSourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary underline underline-offset-2 hover:text-primary-hover"
                    >
                      <span>Mở trang gốc</span>
                      <ExternalLink className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                    </a>
                  </div>
                ) : null}

                <div className="rounded-md border border-line bg-surface-muted/50 p-3 text-sm leading-relaxed text-fg whitespace-pre-wrap">
                  {splitHighlightSegments(
                    currentSourceLoaded.noi_dung,
                    sourceSelection.trichNguyenVan,
                  ).map((seg, idx) =>
                    seg.highlighted ? (
                      <mark
                        key={`src-seg-${idx}`}
                        className="rounded-sm bg-warning-bg px-0.5 font-semibold text-fg"
                      >
                        {seg.text}
                      </mark>
                    ) : (
                      <span key={`src-seg-${idx}`}>{seg.text}</span>
                    ),
                  )}
                </div>
              </div>
            ) : null}
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  )
}
