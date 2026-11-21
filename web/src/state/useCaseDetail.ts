import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReviewApiClient } from '../api/client.ts'
import type { ChiTietCa, NhanDinh, PhanHoiDaGhi } from '../api/types.ts'
import { mergeFindingsFeedback } from '../lib/aiReview.ts'
import { requestCaseData, watchForCaseRefresh } from './caseRefresh.ts'

export interface UseCaseDetailResult {
  detail: ChiTietCa | null
  loading: boolean
  error: string | null
  retry: () => void
  orderSelectionReady: boolean
  applyFeedbackToCase: (caId: string, nhanDinhId: string, recorded: PhanHoiDaGhi) => boolean
}

function updateFindingList(
  list: readonly NhanDinh[],
  nhanDinhId: string,
  recorded: PhanHoiDaGhi,
): NhanDinh[] {
  return list.map((item) =>
    item.nhan_dinh_id === nhanDinhId ? { ...item, phan_hoi: recorded } : item,
  )
}

function formatDetailError(err: unknown): string {
  if (err instanceof Error && err.message) {
    return err.message
  }
  return 'Không tải được chi tiết ca bệnh.'
}

/** Nạp và giữ đệm chi tiết ca trong phiên, không chạy lại khi ghi phản hồi. */
export function useCaseDetail(
  client: ReviewApiClient,
  selectedCaseId: string | null,
): UseCaseDetailResult {
  const [cache, setCache] = useState<Record<string, ChiTietCa>>({})
  const [loadingByCase, setLoadingByCase] = useState<Record<string, boolean>>({})
  const [errorByCase, setErrorByCase] = useState<Record<string, string>>({})
  const [validation, setValidation] = useState({ client, caId: selectedCaseId, ready: false })
  const cacheRef = useRef<Record<string, ChiTietCa>>({})
  const retryRef = useRef<(() => void) | null>(null)
  const feedbackDuringLoad = useRef<{ caId: string; notes: Record<string, PhanHoiDaGhi> } | null>(null)
  const isCurrentValidation = validation.caId === selectedCaseId && validation.client === client
  if (!isCurrentValidation) setValidation({ client, caId: selectedCaseId, ready: false })

  useEffect(() => {
    if (!selectedCaseId) {
      return
    }
    const lifetime = new AbortController()
    let inFlight = false
    let lastRequestAt = Date.now()
    const caId = selectedCaseId

    const clearError = () => setErrorByCase((prev) => {
      if (!(caId in prev)) return prev
      const next = { ...prev }
      delete next[caId]
      return next
    })
    const load = (background: boolean) => {
      if (inFlight) return
      inFlight = true
      lastRequestAt = Date.now()
      const localFeedback = { caId, notes: {} as Record<string, PhanHoiDaGhi> }
      feedbackDuringLoad.current = localFeedback
      if (!background) {
        setLoadingByCase((prev) => ({ ...prev, [caId]: true }))
        clearError()
      }

      void requestCaseData(lifetime.signal, (signal) => client.getCase(caId, { signal }))
        .then((res) => {
          if (lifetime.signal.aborted) return
          const updated = Object.keys(localFeedback.notes).length > 0 ? {
            ...res, nhan_dinh: {
              ...res.nhan_dinh, ...mergeFindingsFeedback(res.nhan_dinh, localFeedback.notes),
            },
          } : res
          cacheRef.current = { ...cacheRef.current, [caId]: updated }
          setCache((prev) => ({ ...prev, [caId]: updated }))
          setValidation((prev) => prev.caId === caId && prev.client === client && !prev.ready
            ? { ...prev, ready: true } : prev)
          clearError()
        })
        .catch((err: unknown) => {
          if (lifetime.signal.aborted) return
          if (background) console.warn('Làm mới chi tiết y lệnh thất bại.')
          else setErrorByCase((prev) => ({ ...prev, [caId]: formatDetailError(err) }))
        })
        .finally(() => {
          inFlight = false
          if (feedbackDuringLoad.current === localFeedback) feedbackDuringLoad.current = null
          if (!lifetime.signal.aborted && !background) {
            setLoadingByCase((prev) => ({ ...prev, [caId]: false }))
          }
        })
    }

    retryRef.current = () => load(false)
    load(Boolean(cacheRef.current[caId]))
    const stop = watchForCaseRefresh(
      () => load(true),
      () => lastRequestAt,
    )
    return () => {
      lifetime.abort()
      retryRef.current = null
      feedbackDuringLoad.current = null
      stop()
    }
  }, [client, selectedCaseId])

  const retry = useCallback(() => retryRef.current?.(), [])

  const applyFeedbackToCase = useCallback(
    (caId: string, nhanDinhId: string, recorded: PhanHoiDaGhi): boolean => {
      const pending = feedbackDuringLoad.current
      if (pending?.caId === caId) pending.notes[nhanDinhId] = recorded
      const current = cacheRef.current[caId]
      if (!current) {
        return false
      }
      const nextCanChuY = updateFindingList(current.nhan_dinh.can_chu_y, nhanDinhId, recorded)
      const nextDat = updateFindingList(current.nhan_dinh.dat, nhanDinhId, recorded)
      const updated: ChiTietCa = {
        ...current,
        nhan_dinh: {
          ...current.nhan_dinh,
          can_chu_y: nextCanChuY,
          dat: nextDat,
        },
      }
      cacheRef.current = { ...cacheRef.current, [caId]: updated }
      setCache((prev) => ({ ...prev, [caId]: updated }))

      return nextCanChuY.length > 0 && nextCanChuY.every((item) => item.phan_hoi !== null)
    },
    [],
  )

  const detail = selectedCaseId ? (cache[selectedCaseId] ?? null) : null
  const loading = selectedCaseId ? Boolean(loadingByCase[selectedCaseId]) : false
  const error = selectedCaseId ? (errorByCase[selectedCaseId] ?? null) : null

  return {
    detail,
    loading,
    error,
    retry,
    orderSelectionReady: isCurrentValidation && validation.ready,
    applyFeedbackToCase,
  }
}
