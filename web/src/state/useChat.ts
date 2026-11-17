import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReviewApiClient } from '../api/client.ts'
import type { LichSuHoiDapItem, TraLoi, TrangThaiTraLoi } from '../api/types.ts'
import { shouldAcceptAssistantReply } from '../lib/assistant.ts'

export const GLOBAL_CHAT_ID = '__global__'

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
    }

export interface UseChatResult {
  getMessages: (caId: string) => ChatMessage[]
  isSending: (caId: string) => boolean
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

function toHistory(messages: readonly ChatMessage[]): LichSuHoiDapItem[] {
  return messages.map((msg) =>
    msg.vai === 'nguoi_dung'
      ? { vai: 'nguoi_dung', noi_dung: msg.noi_dung }
      : { vai: 'he_thong', noi_dung: msg.tra_loi.noi_dung },
  )
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
  const [askedCaseIds, setAskedCaseIds] = useState<string[]>([])
  const [activityByCase, setActivityByCase] = useState<Record<string, string>>({})

  const messagesRef = useRef<Record<string, ChatMessage[]>>({})
  const sendingRef = useRef<Record<string, boolean>>({})
  const hasExplicitActiveCase = activeCaseId !== undefined
  const activeCaseRef = useRef<string | null>(activeCaseId ?? null)
  const seqByCaseRef = useRef<Record<string, number>>({})
  const controllersRef = useRef<Record<string, AbortController | undefined>>({})
  const lastQueryByCaseRef = useRef<
    Record<string, { question: string; nhanDinhId: string | null } | undefined>
  >({})
  const nextIdRef = useRef<number>(1)

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
  }, [activeCaseId])

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
      const apiHistory = toHistory(prevHistory)

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

      controllersRef.current[caId]?.abort()
      const controller = new AbortController()
      controllersRef.current[caId] = controller

      sendingRef.current = { ...sendingRef.current, [caId]: true }
      setSendingByCase((prev) => ({ ...prev, [caId]: true }))

      let reply: TraLoi | null = null
      try {
        reply = await client.ask(
          caId,
          {
            cau_hoi: question,
            lich_su: apiHistory,
            nhan_dinh_id: nhanDinhId,
          },
          { signal: controller.signal },
        )
      } catch (err: unknown) {
        if (isAbortError(err) || controller.signal.aborted) {
          if (seqByCaseRef.current[caId] === requestSeq) {
            sendingRef.current = { ...sendingRef.current, [caId]: false }
            setSendingByCase((prev) => ({ ...prev, [caId]: false }))
          }
          return
        }
        const message =
          err instanceof Error && err.message
            ? err.message
            : 'Không thể gửi câu hỏi tới máy chủ.'
        reply = {
          trang_thai: 'loi',
          noi_dung: message,
          trich_dan: [],
          cong_cu_da_goi: [],
        }
      } finally {
        if (controllersRef.current[caId] === controller) {
          controllersRef.current[caId] = undefined
        }
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
      }

      if (!accepted || reply === null) {
        return
      }

      const assistantMsg: ChatMessage = {
        id: createId('assistant'),
        vai: 'he_thong',
        tra_loi: reply,
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
    controllersRef.current[caId]?.abort()
    controllersRef.current[caId] = undefined
    sendingRef.current = { ...sendingRef.current, [caId]: false }
    setSendingByCase((prev) => ({ ...prev, [caId]: false }))
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
      controllersRef.current[caId]?.abort()
      controllersRef.current[caId] = undefined
      sendingRef.current = { ...sendingRef.current, [caId]: false }
      messagesRef.current = { ...messagesRef.current, [caId]: [] }
      setSendingByCase((prev) => ({ ...prev, [caId]: false }))
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
    getLastStatus,
    askedCaseIds,
    getLastActivity,
    sendQuestion,
    stopQuestion,
    retryLastQuestion,
    clearChat,
  }
}
