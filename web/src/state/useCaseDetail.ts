import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReviewApiClient } from '../api/client.ts'
import type { ChiTietCa, NhanDinh, PhanHoiDaGhi } from '../api/types.ts'

export interface UseCaseDetailResult {
  detail: ChiTietCa | null
  loading: boolean
  error: string | null
  retry: () => void
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
  const [retryMap, setRetryMap] = useState<Record<string, number>>({})
  const cacheRef = useRef<Record<string, ChiTietCa>>({})

  const retryCount = selectedCaseId ? (retryMap[selectedCaseId] ?? 0) : 0

  useEffect(() => {
    if (!selectedCaseId) {
      return
    }
    if (cacheRef.current[selectedCaseId]) {
      return
    }

    let cancelled = false
    const caId = selectedCaseId

    setLoadingByCase((prev) => ({ ...prev, [caId]: true }))
    setErrorByCase((prev) => {
      if (!(caId in prev)) {
        return prev
      }
      const next = { ...prev }
      delete next[caId]
      return next
    })

    client
      .getCase(caId)
      .then((res) => {
        if (cancelled) {
          return
        }
        cacheRef.current = { ...cacheRef.current, [caId]: res }
        setCache((prev) => ({ ...prev, [caId]: res }))
        setLoadingByCase((prev) => ({ ...prev, [caId]: false }))
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        setErrorByCase((prev) => ({ ...prev, [caId]: formatDetailError(err) }))
        setLoadingByCase((prev) => ({ ...prev, [caId]: false }))
      })

    return () => {
      cancelled = true
    }
  }, [client, selectedCaseId, retryCount])

  const retry = useCallback(() => {
    if (!selectedCaseId) {
      return
    }
    setRetryMap((prev) => ({
      ...prev,
      [selectedCaseId]: (prev[selectedCaseId] ?? 0) + 1,
    }))
  }, [selectedCaseId])

  const applyFeedbackToCase = useCallback(
    (caId: string, nhanDinhId: string, recorded: PhanHoiDaGhi): boolean => {
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
    applyFeedbackToCase,
  }
}
