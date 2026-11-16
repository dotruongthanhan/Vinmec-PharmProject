import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient } from '../api/index.ts'
import type { ReviewApiClient } from '../api/client.ts'
import type { KetQuaAI, TrangThaiAI } from '../api/types.ts'

export const AI_POLL_INTERVAL_MS = 2000
export const AI_TIMEOUT_MS = 120_000
const AI_TIMEOUT_MESSAGE = 'Bước AI quá thời gian chờ'

export interface UseAiReviewResult {
  trangThai: TrangThaiAI
  ketQua: KetQuaAI | null
  canhBao: string[]
  thoiGianMs: number | null
  chayLai: () => void
}

interface AiRunSnapshot {
  runKey: string
  caId: string
  trangThai: TrangThaiAI
  ketQua: KetQuaAI | null
  canhBao: string[]
  thoiGianMs: number | null
}

/** Khởi động và hỏi thăm trạng thái phân tích AI chạy nền theo ca đang mở. */
export function useAiReview(
  caId: string | null,
  enabled: boolean,
  client: ReviewApiClient = apiClient,
): UseAiReviewResult {
  const [snapshot, setSnapshot] = useState<AiRunSnapshot | null>(null)
  const [seqByCase, setSeqByCase] = useState<Record<string, number>>({})

  const counterRef = useRef<number>(0)
  const pendingForceRunKeyRef = useRef<string | null>(null)

  const activeSeq = caId ? (seqByCase[caId] ?? 0) : 0
  const activeRunKey = caId && enabled ? `${caId}::${activeSeq}` : null

  const activeCaseRef = useRef<string | null>(caId)
  const activeRunKeyRef = useRef<string | null>(activeRunKey)

  useEffect(() => {
    activeCaseRef.current = caId
    activeRunKeyRef.current = activeRunKey
  }, [caId, activeRunKey])

  useEffect(() => {
    if (!caId || !enabled || !activeRunKey) {
      return
    }

    const targetCaId = caId
    const targetRunKey = activeRunKey
    const isRerun = pendingForceRunKeyRef.current === targetRunKey
    const startedAt = Date.now()
    let cancelled = false
    let pollTimer: ReturnType<typeof setTimeout> | null = null
    let timeoutTimer: ReturnType<typeof setTimeout> | null = null

    const clearTimers = () => {
      if (pollTimer !== null) {
        clearTimeout(pollTimer)
        pollTimer = null
      }
      if (timeoutTimer !== null) {
        clearTimeout(timeoutTimer)
        timeoutTimer = null
      }
    }

    const isStillCurrent = (): boolean =>
      !cancelled &&
      activeCaseRef.current === targetCaId &&
      activeRunKeyRef.current === targetRunKey

    const commitSnapshot = (next: Omit<AiRunSnapshot, 'runKey' | 'caId'>) => {
      if (!isStillCurrent()) {
        return
      }
      setSnapshot({
        runKey: targetRunKey,
        caId: targetCaId,
        ...next,
      })
    }

    const handleResult = (res: KetQuaAI): boolean => {
      if (!isStillCurrent()) {
        return true
      }
      if (res.trang_thai === 'xong') {
        clearTimers()
        commitSnapshot({
          trangThai: 'xong',
          ketQua: res,
          canhBao: res.canh_bao,
          thoiGianMs: res.thoi_gian_ms ?? Date.now() - startedAt,
        })
        return true
      }
      if (res.trang_thai === 'loi') {
        clearTimers()
        commitSnapshot({
          trangThai: 'loi',
          ketQua: null,
          canhBao: res.canh_bao,
          thoiGianMs: res.thoi_gian_ms ?? Date.now() - startedAt,
        })
        return true
      }
      if (res.trang_thai === 'tat') {
        clearTimers()
        commitSnapshot({
          trangThai: 'tat',
          ketQua: null,
          canhBao: res.canh_bao,
          thoiGianMs: null,
        })
        return true
      }
      commitSnapshot({
        trangThai: 'dang_chay',
        ketQua: null,
        canhBao: res.canh_bao,
        thoiGianMs: null,
      })
      return false
    }

    const schedulePoll = () => {
      if (!isStillCurrent()) {
        return
      }
      pollTimer = setTimeout(() => {
        if (!isStillCurrent()) {
          return
        }
        if (Date.now() - startedAt >= AI_TIMEOUT_MS) {
          const elapsed = Date.now() - startedAt
          cancelled = true
          clearTimers()
          setSnapshot({
            runKey: targetRunKey,
            caId: targetCaId,
            trangThai: 'loi',
            ketQua: null,
            canhBao: [AI_TIMEOUT_MESSAGE],
            thoiGianMs: elapsed,
          })
          return
        }
        client
          .getAi(targetCaId)
          .then((res) => {
            if (!isStillCurrent()) {
              return
            }
            if (res === null) {
              schedulePoll()
              return
            }
            const stopped = handleResult(res)
            if (!stopped) {
              schedulePoll()
            }
          })
          .catch((err: unknown) => {
            if (!isStillCurrent()) {
              return
            }
            clearTimers()
            const message =
              err instanceof Error && err.message
                ? err.message
                : 'Không thể kiểm tra trạng thái phân tích AI.'
            commitSnapshot({
              trangThai: 'loi',
              ketQua: null,
              canhBao: [message],
              thoiGianMs: Date.now() - startedAt,
            })
          })
      }, AI_POLL_INTERVAL_MS)
    }

    timeoutTimer = setTimeout(() => {
      if (!isStillCurrent()) {
        return
      }
      const elapsed = Date.now() - startedAt
      cancelled = true
      clearTimers()
      setSnapshot({
        runKey: targetRunKey,
        caId: targetCaId,
        trangThai: 'loi',
        ketQua: null,
        canhBao: [AI_TIMEOUT_MESSAGE],
        thoiGianMs: elapsed,
      })
    }, AI_TIMEOUT_MS)

    client
      .startAi(targetCaId, isRerun)
      .then((res) => {
        if (pendingForceRunKeyRef.current === targetRunKey) {
          pendingForceRunKeyRef.current = null
        }
        if (!isStillCurrent()) {
          return
        }
        const stopped = handleResult(res)
        if (!stopped) {
          schedulePoll()
        }
      })
      .catch((err: unknown) => {
        if (pendingForceRunKeyRef.current === targetRunKey) {
          pendingForceRunKeyRef.current = null
        }
        if (!isStillCurrent()) {
          return
        }
        clearTimers()
        const message =
          err instanceof Error && err.message
            ? err.message
            : 'Không thể khởi động phân tích AI.'
        commitSnapshot({
          trangThai: 'loi',
          ketQua: null,
          canhBao: [message],
          thoiGianMs: Date.now() - startedAt,
        })
      })

    return () => {
      cancelled = true
      clearTimers()
    }
  }, [client, caId, enabled, activeRunKey])

  const chayLai = useCallback(() => {
    if (!caId || !enabled) {
      return
    }
    counterRef.current += 1
    const nextSeq = counterRef.current
    pendingForceRunKeyRef.current = `${caId}::${nextSeq}`
    setSeqByCase((prev) => ({
      ...prev,
      [caId]: nextSeq,
    }))
  }, [caId, enabled])

  if (!caId || !enabled || !activeRunKey) {
    return {
      trangThai: 'tat',
      ketQua: null,
      canhBao: [],
      thoiGianMs: null,
      chayLai,
    }
  }

  if (snapshot && snapshot.runKey === activeRunKey && snapshot.caId === caId) {
    return {
      trangThai: snapshot.trangThai,
      ketQua: snapshot.ketQua,
      canhBao: snapshot.canhBao,
      thoiGianMs: snapshot.thoiGianMs,
      chayLai,
    }
  }

  return {
    trangThai: 'dang_chay',
    ketQua: null,
    canhBao: [],
    thoiGianMs: null,
    chayLai,
  }
}
