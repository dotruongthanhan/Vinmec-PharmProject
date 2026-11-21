import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client.ts'
import type { ReviewApiClient } from '../api/client.ts'
import type {
  BuocAI,
  GuiCauHoi,
  TienTrinhHoiDap,
  TraLoi,
  TrangThaiTraLoi,
} from '../api/types.ts'
import { shouldAcceptAssistantReply } from '../lib/assistant.ts'

export const GLOBAL_CHAT_ID = '__global__'
export const ASK_PROGRESS_POLL_INTERVAL_MS = 1000

export interface AskProgressSnapshot {
  cacBuoc: BuocAI[]
  daChayMs: number | null
}

const EMPTY_ASK_PROGRESS: AskProgressSnapshot = {
  cacBuoc: [],
  daChayMs: null,
}

export type ChatMessage =
  | {
      id: string
      vai: 'nguoi_dung'
      noi_dung: string
      nhan_dinh_id?: string | null
    }
  | {
      id: string
      vai: 'he_thong'
      tra_loi: TraLoi
      cac_buoc?: BuocAI[]
      da_chay_ms?: number | null
    }

export interface UseChatResult {
  getMessages: (caId: string) => ChatMessage[]
  isSending: (caId: string) => boolean
  getProgress: (caId: string) => AskProgressSnapshot
  getLastStatus: (caId: string) => TrangThaiTraLoi | null
  /** Mã phạm vi đã hỏi (kể cả hỏi đáp chung), mới nhất đứng đầu. */
  askedCaseIds: string[]
  /** Thời điểm hỏi gần nhất (ISO) của một phạm vi, hoặc null nếu chưa rõ. */
  getLastActivity: (caId: string) => string | null
  sendQuestion: (caId: string, question: string, nhanDinhId?: string | null) => Promise<void>
  stopQuestion: (caId: string) => void
  retryLastQuestion: (caId: string) => Promise<void>
  clearChat: (caId: string) => void
}

function isDocumentHidden(): boolean {
  return typeof document !== 'undefined' && Boolean(document.hidden)
}

function extractWaitSeconds(err: unknown): number | null {
  if (typeof err === 'object' && err !== null && 'retryAfter' in err) {
    const raw = (err as { retryAfter?: unknown }).retryAfter
    if (typeof raw === 'number' && Number.isFinite(raw) && raw > 0) {
      return Math.ceil(raw)
    }
  }
  if (err instanceof Error && err.message) {
    const match = /(\d+)\s*giây/i.exec(err.message)
    if (match) {
      const parsed = Number(match[1])
      if (Number.isFinite(parsed) && parsed > 0) {
        return parsed
      }
    }
  }
  return null
}

/** Tạo thông báo lỗi thân thiện cho người dùng, nhấn mạnh thời gian chờ khi gặp 429. */
export function formatAskErrorMessage(err: unknown): string {
  const status =
    err instanceof ApiError
      ? err.status
      : typeof err === 'object' && err !== null && 'status' in err
        ? (err as { status?: unknown }).status
        : undefined
  const ma =
    err instanceof ApiError
      ? err.ma
      : typeof err === 'object' && err !== null && 'ma' in err
        ? (err as { ma?: unknown }).ma
        : undefined

  if (status === 429) {
    const seconds = extractWaitSeconds(err) ?? 30
    if (ma === 'het_ngan_sach_ngay') {
      return `Hệ thống đã hết lượt trợ lý AI trong ngày. Vui lòng thử lại sau ${seconds} giây.`
    }
    return `Bạn đã gửi quá nhiều câu hỏi. Vui lòng chờ ${seconds} giây rồi thử lại.`
  }

  if (err instanceof Error && err.message) {
    return err.message
  }
  return 'Không thể gửi câu hỏi tới máy chủ.'
}

function isAbortError(err: unknown): boolean {
  return (
    (err instanceof DOMException && err.name === 'AbortError') ||
    (err instanceof Error && err.name === 'AbortError')
  )
}

/** Quản lý hội thoại hỏi đáp tách biệt theo từng ca bệnh, hỗ trợ huỷ yêu cầu và chống ghi nhầm khi đổi ca. */
export function useChat(
  client: ReviewApiClient,
  activeCaseId?: string | null,
): UseChatResult {
  const [messagesByCase, setMessagesByCase] = useState<Record<string, ChatMessage[]>>({})
  const [sendingByCase, setSendingByCase] = useState<Record<string, boolean>>({})
  const [progressByCase, setProgressByCase] = useState<Record<string, AskProgressSnapshot>>({})
  const [askedCaseIds, setAskedCaseIds] = useState<string[]>([])
  const [activityByCase, setActivityByCase] = useState<Record<string, string>>({})

  const messagesRef = useRef<Record<string, ChatMessage[]>>({})
  const sendingRef = useRef<Record<string, boolean>>({})
  const hasExplicitActiveCase = activeCaseId !== undefined
  const activeCaseRef = useRef<string | null>(activeCaseId ?? null)
  const seqByCaseRef = useRef<Record<string, number>>({})
  const controllersRef = useRef<Record<string, AbortController | undefined>>({})
  const progressPollCleanupRef = useRef<Record<string, (() => void) | undefined>>({})
  const lastQueryByCaseRef = useRef<
    Record<string, { question: string; nhanDinhId: string | null } | undefined>
  >({})
  const nextIdRef = useRef<number>(1)

  useEffect(() => () => {
    for (const cleanup of Object.values(progressPollCleanupRef.current)) cleanup?.()
    progressPollCleanupRef.current = {}
    for (const controller of Object.values(controllersRef.current)) controller?.abort()
    controllersRef.current = {}
    messagesRef.current = {}
    sendingRef.current = {}
    lastQueryByCaseRef.current = {}
  }, [])

  useEffect(() => {
    if (!client.getConversations) {
      return
    }
    let cancelled = false
    client
      .getConversations()
      .then((grouped) => {
        if (cancelled || !grouped || typeof grouped !== 'object') {
          return
        }
        const restored: Record<string, ChatMessage[]> = {}
        const restoredActivity: Record<string, string> = {}
        for (const [caId, turns] of Object.entries(grouped)) {
          if (!Array.isArray(turns) || turns.length === 0) {
            continue
          }
          const list: ChatMessage[] = []
          for (const turn of turns) {
            if (!turn || typeof turn.cau_hoi !== 'string' || !turn.tra_loi) {
              continue
            }
            const uId = `restored-u-${nextIdRef.current}`
            nextIdRef.current += 1
            const aId = `restored-a-${nextIdRef.current}`
            nextIdRef.current += 1
            list.push({ id: uId, vai: 'nguoi_dung', noi_dung: turn.cau_hoi })
            list.push({ id: aId, vai: 'he_thong', tra_loi: turn.tra_loi })
          }
          if (list.length > 0) {
            restored[caId] = list
            const lastTurn = turns[turns.length - 1]
            if (lastTurn && typeof lastTurn.thoi_diem === 'string' && lastTurn.thoi_diem) {
              restoredActivity[caId] = lastTurn.thoi_diem
            }
          }
        }
        if (Object.keys(restored).length > 0) {
          messagesRef.current = { ...restored, ...messagesRef.current }
          setMessagesByCase((prev) => ({ ...restored, ...prev }))
          setActivityByCase((prev) => ({ ...restoredActivity, ...prev }))
          setAskedCaseIds((prev) => {
            const extra = Object.keys(restored).filter((id) => !prev.includes(id))
            return [...prev, ...extra]
          })
        }
      })
      .catch(() => {
        // Bỏ qua lỗi khi không tải được lịch sử cũ
      })
    return () => {
      cancelled = true
    }
  }, [client])

  useEffect(() => {
    activeCaseRef.current = activeCaseId ?? null
    if (!hasExplicitActiveCase) {
      return
    }
    for (const [caId, cleanup] of Object.entries(progressPollCleanupRef.current)) {
      if (caId !== activeCaseId) {
        cleanup?.()
        progressPollCleanupRef.current[caId] = undefined
      }
    }
  }, [activeCaseId, hasExplicitActiveCase])

  const createId = useCallback((prefix: string): string => {
    const id = `${prefix}-${nextIdRef.current}`
    nextIdRef.current += 1
    return id
  }, [])

  const getMessages = useCallback(
    (caId: string): ChatMessage[] => messagesByCase[caId] ?? [],
    [messagesByCase],
  )

  const isSending = useCallback(
    (caId: string): boolean => Boolean(sendingByCase[caId]),
    [sendingByCase],
  )

  const getProgress = useCallback(
    (caId: string): AskProgressSnapshot => progressByCase[caId] ?? EMPTY_ASK_PROGRESS,
    [progressByCase],
  )

  const getLastStatus = useCallback(
    (caId: string): TrangThaiTraLoi | null => {
      const list = messagesByCase[caId]
      if (!list || list.length === 0) {
        return null
      }
      for (let i = list.length - 1; i >= 0; i -= 1) {
        const msg = list[i]
        if (msg.vai === 'he_thong') {
          return msg.tra_loi.trang_thai
        }
      }
      return null
    },
    [messagesByCase],
  )

  const executeAsk = useCallback(
    async (
      caId: string,
      question: string,
      nhanDinhId: string | null,
      appendUserMessage: boolean,
    ): Promise<void> => {
      if (!question || sendingRef.current[caId]) {
        return
      }

      const prevHistory = messagesRef.current[caId] ?? []

      if (appendUserMessage) {
        const userMsg: ChatMessage = {
          id: createId('user'),
          vai: 'nguoi_dung',
          noi_dung: question,
          nhan_dinh_id: nhanDinhId,
        }
        const withUser = [...prevHistory, userMsg]
        messagesRef.current = { ...messagesRef.current, [caId]: withUser }
        setMessagesByCase((prev) => ({ ...prev, [caId]: [...(prev[caId] ?? []), userMsg] }))
      }

      lastQueryByCaseRef.current[caId] = { question, nhanDinhId }
      setAskedCaseIds((prev) => [caId, ...prev.filter((id) => id !== caId)])
      const askedAt = new Date().toISOString()
      setActivityByCase((prev) => ({ ...prev, [caId]: askedAt }))

      const requestSeq = (seqByCaseRef.current[caId] ?? 0) + 1
      seqByCaseRef.current[caId] = requestSeq

      progressPollCleanupRef.current[caId]?.()
      progressPollCleanupRef.current[caId] = undefined
      controllersRef.current[caId]?.abort()
      const controller = new AbortController()
      controllersRef.current[caId] = controller

      sendingRef.current = { ...sendingRef.current, [caId]: true }
      setSendingByCase((prev) => ({ ...prev, [caId]: true }))
      setProgressByCase((prev) => ({ ...prev, [caId]: EMPTY_ASK_PROGRESS }))

      let lastPolledSteps: BuocAI[] = []
      let lastPolledDaChayMs: number | null = null
      let pollStopped = false
      let pollInFlight = false
      let pollTimer: ReturnType<typeof setTimeout> | null = null
      let pollAbortController: AbortController | null = null

      const isPollingAllowed = (): boolean =>
        !pollStopped &&
        !controller.signal.aborted &&
        Boolean(sendingRef.current[caId]) &&
        seqByCaseRef.current[caId] === requestSeq &&
        (!hasExplicitActiveCase || activeCaseRef.current === caId)

      const clearPollTimer = () => {
        if (pollTimer !== null) {
          clearTimeout(pollTimer)
          pollTimer = null
        }
      }

      const applyProgress = (progress: TienTrinhHoiDap) => {
        if (!isPollingAllowed()) {
          return
        }
        if (progress.cac_buoc.length > 0 || progress.da_chay_ms !== null) {
          lastPolledSteps = progress.cac_buoc
          lastPolledDaChayMs = progress.da_chay_ms
          setProgressByCase((prev) => ({
            ...prev,
            [caId]: {
              cacBuoc: progress.cac_buoc,
              daChayMs: progress.da_chay_ms,
            },
          }))
        }
      }

      const stopPolling = () => {
        pollStopped = true
        clearPollTimer()
        pollAbortController?.abort()
        pollAbortController = null
        if (typeof document !== 'undefined' && typeof document.removeEventListener === 'function') {
          document.removeEventListener('visibilitychange', onVisibilityChange)
        }
      }

      const scheduleNextPoll = () => {
        clearPollTimer()
        if (!isPollingAllowed() || isDocumentHidden()) {
          return
        }
        pollTimer = setTimeout(runPoll, ASK_PROGRESS_POLL_INTERVAL_MS)
      }

      const runPoll = () => {
        pollTimer = null
        if (!isPollingAllowed() || isDocumentHidden() || pollInFlight) {
          return
        }
        if (typeof client.getAskProgress !== 'function') {
          return
        }
        pollInFlight = true
        const reqController = new AbortController()
        pollAbortController = reqController
        void client
          .getAskProgress(caId, { signal: reqController.signal })
          .then((progress) => {
            pollInFlight = false
            if (pollAbortController === reqController) {
              pollAbortController = null
            }
            if (!isPollingAllowed()) {
              return
            }
            applyProgress(progress)
            scheduleNextPoll()
          })
          .catch(() => {
            pollInFlight = false
            if (pollAbortController === reqController) {
              pollAbortController = null
            }
            if (isPollingAllowed()) {
              scheduleNextPoll()
            }
          })
      }

      const onVisibilityChange = () => {
        if (!isPollingAllowed()) {
          stopPolling()
          return
        }
        if (isDocumentHidden()) {
          clearPollTimer()
          return
        }
        if (!pollInFlight) {
          clearPollTimer()
          runPoll()
        }
      }

      progressPollCleanupRef.current[caId] = stopPolling
      if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
        document.addEventListener('visibilitychange', onVisibilityChange)
      }
      scheduleNextPoll()

      let reply: TraLoi | null = null
      let wasAborted = false
      try {
        const payload: Omit<GuiCauHoi, 'lich_su'> = {
          cau_hoi: question,
          nhan_dinh_id: nhanDinhId,
        }
        reply = await client.ask(caId, payload as GuiCauHoi, {
          signal: controller.signal,
        })
      } catch (err: unknown) {
        if (isAbortError(err) || controller.signal.aborted) {
          wasAborted = true
        } else {
          const message = formatAskErrorMessage(err)
          reply = {
            trang_thai: 'loi',
            noi_dung: message,
            trich_dan: [],
            cong_cu_da_goi: [],
          }
        }
      } finally {
        stopPolling()
        if (progressPollCleanupRef.current[caId] === stopPolling) {
          progressPollCleanupRef.current[caId] = undefined
        }
      }

      if (wasAborted) {
        if (controllersRef.current[caId] === controller) {
          controllersRef.current[caId] = undefined
        }
        if (seqByCaseRef.current[caId] === requestSeq) {
          sendingRef.current = { ...sendingRef.current, [caId]: false }
          setSendingByCase((prev) => ({ ...prev, [caId]: false }))
          setProgressByCase((prev) => ({ ...prev, [caId]: EMPTY_ASK_PROGRESS }))
        }
        return
      }

      const acceptedBeforeFinal = shouldAcceptAssistantReply({
        requestCaseId: caId,
        activeCaseId: hasExplicitActiveCase ? activeCaseRef.current : caId,
        requestSeq,
        latestSeqForCase: seqByCaseRef.current[caId] ?? 0,
        aborted: controller.signal.aborted,
      })

      if (!acceptedBeforeFinal || reply === null) {
        if (controllersRef.current[caId] === controller) {
          controllersRef.current[caId] = undefined
        }
        if (seqByCaseRef.current[caId] === requestSeq) {
          sendingRef.current = { ...sendingRef.current, [caId]: false }
          setSendingByCase((prev) => ({ ...prev, [caId]: false }))
          setProgressByCase((prev) => ({ ...prev, [caId]: EMPTY_ASK_PROGRESS }))
        }
        return
      }

      let finalSteps: BuocAI[] = lastPolledSteps
      let finalDaChayMs: number | null = lastPolledDaChayMs
      if (typeof client.getAskProgress === 'function') {
        try {
          const finalProgress = await client.getAskProgress(caId, {
            signal: controller.signal,
          })
          if (finalProgress.cac_buoc.length > 0) {
            finalSteps = finalProgress.cac_buoc
          }
          if (finalProgress.da_chay_ms !== null) {
            finalDaChayMs = finalProgress.da_chay_ms
          }
        } catch {
          // Không chặn hiển thị câu trả lời nếu đọc tiến trình lần cuối gặp lỗi.
        }
      }

      if (controllersRef.current[caId] === controller) {
        controllersRef.current[caId] = undefined
      }

      const accepted = shouldAcceptAssistantReply({
        requestCaseId: caId,
        activeCaseId: hasExplicitActiveCase ? activeCaseRef.current : caId,
        requestSeq,
        latestSeqForCase: seqByCaseRef.current[caId] ?? 0,
        aborted: controller.signal.aborted,
      })

      if (seqByCaseRef.current[caId] === requestSeq) {
        sendingRef.current = { ...sendingRef.current, [caId]: false }
        setSendingByCase((prev) => ({ ...prev, [caId]: false }))
        setProgressByCase((prev) => ({ ...prev, [caId]: EMPTY_ASK_PROGRESS }))
      }

      if (!accepted) {
        return
      }

      const assistantMsg: ChatMessage = {
        id: createId('assistant'),
        vai: 'he_thong',
        tra_loi: reply,
        ...(finalSteps.length > 0 ? { cac_buoc: finalSteps } : {}),
        ...(finalDaChayMs !== null ? { da_chay_ms: finalDaChayMs } : {}),
      }
      const latestForCase = messagesRef.current[caId] ?? []
      const withReply = [...latestForCase, assistantMsg]
      messagesRef.current = { ...messagesRef.current, [caId]: withReply }
      setMessagesByCase((prev) => ({
        ...prev,
        [caId]: [...(prev[caId] ?? []), assistantMsg],
      }))
    },
    [client, createId, hasExplicitActiveCase],
  )

  const sendQuestion = useCallback(
    async (
      caId: string,
      rawQuestion: string,
      nhanDinhId: string | null = null,
    ): Promise<void> => {
      const question = rawQuestion.trim()
      if (!question) {
        return
      }
      await executeAsk(caId, question, nhanDinhId, true)
    },
    [executeAsk],
  )

  const stopQuestion = useCallback((caId: string) => {
    seqByCaseRef.current[caId] = (seqByCaseRef.current[caId] ?? 0) + 1
    progressPollCleanupRef.current[caId]?.()
    progressPollCleanupRef.current[caId] = undefined
    controllersRef.current[caId]?.abort()
    controllersRef.current[caId] = undefined
    sendingRef.current = { ...sendingRef.current, [caId]: false }
    setSendingByCase((prev) => ({ ...prev, [caId]: false }))
    setProgressByCase((prev) => ({ ...prev, [caId]: EMPTY_ASK_PROGRESS }))
  }, [])

  const retryLastQuestion = useCallback(
    async (caId: string): Promise<void> => {
      if (sendingRef.current[caId]) {
        return
      }
      const lastQuery = lastQueryByCaseRef.current[caId]
      if (!lastQuery) {
        return
      }
      const current = messagesRef.current[caId] ?? []
      const last = current[current.length - 1]
      const cleaned =
        last && last.vai === 'he_thong' && last.tra_loi.trang_thai === 'loi'
          ? current.slice(0, -1)
          : current
      messagesRef.current = { ...messagesRef.current, [caId]: cleaned }
      setMessagesByCase((prev) => ({ ...prev, [caId]: cleaned }))
      await executeAsk(caId, lastQuery.question, lastQuery.nhanDinhId, false)
    },
    [executeAsk],
  )

  const clearChat = useCallback(
    (caId: string) => {
      seqByCaseRef.current[caId] = (seqByCaseRef.current[caId] ?? 0) + 1
      progressPollCleanupRef.current[caId]?.()
      progressPollCleanupRef.current[caId] = undefined
      controllersRef.current[caId]?.abort()
      controllersRef.current[caId] = undefined
      sendingRef.current = { ...sendingRef.current, [caId]: false }
      messagesRef.current = { ...messagesRef.current, [caId]: [] }
      setSendingByCase((prev) => ({ ...prev, [caId]: false }))
      setProgressByCase((prev) => ({ ...prev, [caId]: EMPTY_ASK_PROGRESS }))
      setMessagesByCase((prev) => ({ ...prev, [caId]: [] }))
      setAskedCaseIds((prev) => prev.filter((id) => id !== caId))
      setActivityByCase((prev) => {
        const { [caId]: _removed, ...rest } = prev
        return rest
      })
      if (client.clearConversation) {
        void client.clearConversation(caId).catch(() => {})
      }
    },
    [client],
  )

  const getLastActivity = useCallback(
    (caId: string): string | null => activityByCase[caId] ?? null,
    [activityByCase],
  )

  return {
    getMessages,
    isSending,
    getProgress,
    getLastStatus,
    askedCaseIds,
    getLastActivity,
    sendQuestion,
    stopQuestion,
    retryLastQuestion,
    clearChat,
  }
}
