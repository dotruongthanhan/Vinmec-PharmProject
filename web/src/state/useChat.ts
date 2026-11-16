import { useCallback, useRef, useState } from 'react'
import type { ReviewApiClient } from '../api/client.ts'
import type { LichSuHoiDapItem, TraLoi } from '../api/types.ts'

export type ChatMessage =
  | {
      id: string
      vai: 'nguoi_dung'
      noi_dung: string
    }
  | {
      id: string
      vai: 'he_thong'
      tra_loi: TraLoi
    }

export interface UseChatResult {
  getMessages: (caId: string) => ChatMessage[]
  isSending: (caId: string) => boolean
  sendQuestion: (caId: string, question: string) => Promise<void>
  clearChat: (caId: string) => void
}

function toHistory(messages: readonly ChatMessage[]): LichSuHoiDapItem[] {
  return messages.map((msg) =>
    msg.vai === 'nguoi_dung'
      ? { vai: 'nguoi_dung', noi_dung: msg.noi_dung }
      : { vai: 'he_thong', noi_dung: msg.tra_loi.noi_dung },
  )
}

/** Quản lý hội thoại hỏi thêm tách biệt theo từng ca bệnh. */
export function useChat(client: ReviewApiClient): UseChatResult {
  const [messagesByCase, setMessagesByCase] = useState<Record<string, ChatMessage[]>>({})
  const [sendingByCase, setSendingByCase] = useState<Record<string, boolean>>({})
  const messagesRef = useRef<Record<string, ChatMessage[]>>({})
  const sendingRef = useRef<Record<string, boolean>>({})
  const nextIdRef = useRef<number>(1)

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

  const sendQuestion = useCallback(
    async (caId: string, rawQuestion: string): Promise<void> => {
      const question = rawQuestion.trim()
      if (!question || sendingRef.current[caId]) {
        return
      }

      sendingRef.current = { ...sendingRef.current, [caId]: true }
      const prevHistory = messagesRef.current[caId] ?? []
      const apiHistory = toHistory(prevHistory)
      const userMsg: ChatMessage = {
        id: createId('user'),
        vai: 'nguoi_dung',
        noi_dung: question,
      }

      const withUser = [...prevHistory, userMsg]
      messagesRef.current = { ...messagesRef.current, [caId]: withUser }
      setMessagesByCase((prev) => ({ ...prev, [caId]: [...(prev[caId] ?? []), userMsg] }))
      setSendingByCase((prev) => ({ ...prev, [caId]: true }))

      let reply: TraLoi
      try {
        reply = await client.ask(caId, {
          cau_hoi: question,
          lich_su: apiHistory,
        })
      } catch (err: unknown) {
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
      }

      const assistantMsg: ChatMessage = {
        id: createId('assistant'),
        vai: 'he_thong',
        tra_loi: reply,
      }
      const latestForCase = messagesRef.current[caId] ?? []
      const withReply = [...latestForCase, assistantMsg]
      messagesRef.current = { ...messagesRef.current, [caId]: withReply }
      sendingRef.current = { ...sendingRef.current, [caId]: false }
      setMessagesByCase((prev) => ({
        ...prev,
        [caId]: [...(prev[caId] ?? []), assistantMsg],
      }))
      setSendingByCase((prev) => ({ ...prev, [caId]: false }))
    },
    [client, createId],
  )

  const clearChat = useCallback((caId: string) => {
    messagesRef.current = { ...messagesRef.current, [caId]: [] }
    setMessagesByCase((prev) => ({ ...prev, [caId]: [] }))
  }, [])

  return {
    getMessages,
    isSending,
    sendQuestion,
    clearChat,
  }
}
