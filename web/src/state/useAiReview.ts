import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient } from '../api/index.ts'
import type { ReviewApiClient } from '../api/client.ts'
import type { BuocAI, KetQuaAI, TrangThaiAI } from '../api/types.ts'

export const AI_POLL_INTERVAL_MS = 1500
export const AI_TIMEOUT_MS = 120_000
const AI_TIMEOUT_MESSAGE = 'Bước AI quá thời gian chờ'

export interface UseAiReviewResult {
  trangThai: TrangThaiAI
  ketQua: KetQuaAI | null
  canhBao: string[]
  thoiGianMs: number | null
  cacBuoc: BuocAI[]
  daChayMs: number | null
  thuongLeMs: number | null
  chayLai: () => void
}

export interface AiRunSnapshot {
  runKey: string
  caId: string
  trangThai: TrangThaiAI
  ketQua: KetQuaAI | null
  canhBao: string[]
  thoiGianMs: number | null
  cacBuoc: BuocAI[]
  daChayMs: number | null
  thuongLeMs: number | null
}

export interface AiPollingSessionOptions {
  caId: string
  runKey: string
  isRerun: boolean
  client: ReviewApiClient
  isCurrent: () => boolean
  onUpdate: (snapshot: AiRunSnapshot) => void
}

function isDocumentHidden(): boolean {
  return typeof document !== 'undefined' && Boolean(document.hidden)
}

function readSteps(res: KetQuaAI): BuocAI[] {
  return Array.isArray(res.cac_buoc) ? res.cac_buoc : []
}

function readOptionalMs(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** Điều phối vòng đời một lượt phân tích AI: khởi động, hỏi lại mỗi 1500 ms, tạm dừng khi ẩn tab và chống đua ca. */
export function runAiReviewSession({
  caId,
  runKey,
  isRerun,
  client,
  isCurrent,
  onUpdate,
}: AiPollingSessionOptions): () => void {
  const startedAt = Date.now()
  let cancelled = false
  let finished = false
  let startDone = false
  let pollInFlight = false
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

  const isStillCurrent = (): boolean => !cancelled && isCurrent()

  const emit = (next: Omit<AiRunSnapshot, 'runKey' | 'caId'>) => {
    if (!isStillCurrent()) {
      return
    }
    onUpdate({
      runKey,
      caId,
      ...next,
    })
  }

  const handleResult = (res: KetQuaAI): boolean => {
    if (!isStillCurrent()) {
      return true
    }
    const cacBuoc = readSteps(res)
    const daChayMs = readOptionalMs(res.da_chay_ms)
    const thuongLeMs = readOptionalMs(res.thuong_le_ms)
    const canhBao = Array.isArray(res.canh_bao) ? res.canh_bao : []

    if (res.trang_thai === 'xong') {
      finished = true
      clearTimers()
      const totalMs = res.thoi_gian_ms ?? daChayMs ?? Date.now() - startedAt
      emit({
        trangThai: 'xong',
        ketQua: res,
        canhBao,
        thoiGianMs: totalMs,
        cacBuoc,
        daChayMs: daChayMs ?? totalMs,
        thuongLeMs,
      })
      return true
    }

    if (res.trang_thai === 'loi') {
      finished = true
      clearTimers()
      const totalMs = res.thoi_gian_ms ?? daChayMs ?? Date.now() - startedAt
      emit({
        trangThai: 'loi',
        ketQua: null,
        canhBao,
        thoiGianMs: totalMs,
        cacBuoc,
        daChayMs: daChayMs ?? totalMs,
        thuongLeMs,
      })
      return true
    }

    if (res.trang_thai === 'tat') {
      finished = true
      clearTimers()
      emit({
        trangThai: 'tat',
        ketQua: null,
        canhBao,
        thoiGianMs: null,
        cacBuoc: [],
        daChayMs: null,
        thuongLeMs: null,
      })
      return true
    }

    emit({
      trangThai: 'dang_chay',
      ketQua: null,
      canhBao,
      thoiGianMs: null,
      cacBuoc,
      daChayMs,
      thuongLeMs,
    })
    return false
  }

  const triggerTimeout = () => {
    if (!isStillCurrent() || finished) {
      return
    }
    const elapsed = Date.now() - startedAt
    finished = true
    cancelled = true
    clearTimers()
    onUpdate({
      runKey,
      caId,
      trangThai: 'loi',
      ketQua: null,
      canhBao: [AI_TIMEOUT_MESSAGE],
      thoiGianMs: elapsed,
      cacBuoc: [],
      daChayMs: elapsed,
      thuongLeMs: null,
    })
  }

  const runPoll = () => {
    pollTimer = null
    if (!isStillCurrent() || finished || isDocumentHidden() || pollInFlight) {
      return
    }
    if (Date.now() - startedAt >= AI_TIMEOUT_MS) {
      triggerTimeout()
      return
    }
    pollInFlight = true
    client
      .getAi(caId)
      .then((res) => {
        pollInFlight = false
        if (!isStillCurrent() || finished) {
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
        pollInFlight = false
        if (!isStillCurrent() || finished) {
          return
        }
        finished = true
        clearTimers()
        const message =
          err instanceof Error && err.message
            ? err.message
            : 'Không thể kiểm tra trạng thái phân tích AI.'
        const elapsed = Date.now() - startedAt
        emit({
          trangThai: 'loi',
          ketQua: null,
          canhBao: [message],
          thoiGianMs: elapsed,
          cacBuoc: [],
          daChayMs: elapsed,
          thuongLeMs: null,
        })
      })
  }

  const schedulePoll = () => {
    if (pollTimer !== null) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    if (!isStillCurrent() || finished || isDocumentHidden()) {
      return
    }
    pollTimer = setTimeout(runPoll, AI_POLL_INTERVAL_MS)
  }

  const onVisibilityChange = () => {
    if (!isStillCurrent() || finished) {
      return
    }
    if (isDocumentHidden()) {
      if (pollTimer !== null) {
        clearTimeout(pollTimer)
        pollTimer = null
      }
      return
    }
    if (startDone && !pollInFlight) {
      if (pollTimer !== null) {
        clearTimeout(pollTimer)
        pollTimer = null
      }
      runPoll()
    }
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange)
  }

  timeoutTimer = setTimeout(triggerTimeout, AI_TIMEOUT_MS)

  client
    .startAi(caId, isRerun)
    .then((res) => {
      startDone = true
      if (!isStillCurrent() || finished) {
        return
      }
      const stopped = handleResult(res)
      if (!stopped) {
        schedulePoll()
      }
    })
    .catch((err: unknown) => {
      startDone = true
      if (!isStillCurrent() || finished) {
        return
      }
      finished = true
      clearTimers()
      const message =
        err instanceof Error && err.message
          ? err.message
          : 'Không thể khởi động phân tích AI.'
      const elapsed = Date.now() - startedAt
      emit({
        trangThai: 'loi',
        ketQua: null,
        canhBao: [message],
        thoiGianMs: elapsed,
        cacBuoc: [],
        daChayMs: elapsed,
        thuongLeMs: null,
      })
    })

  return () => {
    cancelled = true
    clearTimers()
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }
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
    if (isRerun) {
      pendingForceRunKeyRef.current = null
    }

    return runAiReviewSession({
      caId: targetCaId,
      runKey: targetRunKey,
      isRerun,
      client,
      isCurrent: () =>
        activeCaseRef.current === targetCaId && activeRunKeyRef.current === targetRunKey,
      onUpdate: setSnapshot,
    })
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
      cacBuoc: [],
      daChayMs: null,
      thuongLeMs: null,
      chayLai,
    }
  }

  if (snapshot && snapshot.runKey === activeRunKey && snapshot.caId === caId) {
    return {
      trangThai: snapshot.trangThai,
      ketQua: snapshot.ketQua,
      canhBao: snapshot.canhBao,
      thoiGianMs: snapshot.thoiGianMs,
      cacBuoc: snapshot.cacBuoc,
      daChayMs: snapshot.daChayMs,
      thuongLeMs: snapshot.thuongLeMs,
      chayLai,
    }
  }

  return {
    trangThai: 'dang_chay',
    ketQua: null,
    canhBao: [],
    thoiGianMs: null,
    cacBuoc: [],
    daChayMs: null,
    thuongLeMs: null,
    chayLai,
  }
}
