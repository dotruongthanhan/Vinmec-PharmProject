import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReviewApiClient } from '../api/client.ts'
import type { DanhSachCa } from '../api/types.ts'
import { parseVietnamDate } from '../lib/displayFormat.ts'
import { loadUiPrefs, saveQueueFilter, saveSelectedCaseId } from '../lib/prefs.ts'
import { markCaseAllResponded } from '../lib/queue.ts'
import type { QueueFilter } from '../lib/queue.ts'
import { requestCaseData, watchForCaseRefresh } from './caseRefresh.ts'

export interface UseCasesResult {
  data: DanhSachCa | null
  loading: boolean
  error: string | null
  selectedCaseId: string | null
  filter: QueueFilter
  selectCase: (caId: string) => void
  setFilter: (filter: QueueFilter) => void
  reload: () => void
  refresh: () => void
  updatedAt: Date | null
  markAllResponded: (caId: string, allResponded: boolean) => void
}

function formatLoadError(err: unknown): string {
  if (err instanceof Error && err.message) {
    return err.message
  }
  return 'Không tải được danh sách ca thẩm định.'
}

/** Quản lý danh sách ca hàng đợi, bộ lọc và ca đang chọn. */
export function useCases(client: ReviewApiClient): UseCasesResult {
  const [data, setData] = useState<DanhSachCa | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(
    () => loadUiPrefs().selectedCaseId,
  )
  const [filter, setFilterState] = useState<QueueFilter>(() => loadUiPrefs().queueFilter)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const loadRef = useRef<((background: boolean) => void) | null>(null)
  const feedbackDuringLoad = useRef<Map<string, boolean> | null>(null)

  useEffect(() => {
    const lifetime = new AbortController()
    let inFlight = false
    let lastRequestAt = Date.now()

    const load = (background: boolean) => {
      if (inFlight) return
      inFlight = true
      const localFeedback = new Map<string, boolean>()
      feedbackDuringLoad.current = localFeedback
      lastRequestAt = Date.now()
      if (!background) {
        setLoading(true)
        setError(null)
      }

      void requestCaseData(lifetime.signal, (signal) => client.getCases({ signal }))
        .then((res) => {
          if (lifetime.signal.aborted) return
          setData(localFeedback.size ? {
            ...res,
            cases: res.cases.map((item) => {
              const allResponded = localFeedback.get(item.ca_id)
              return allResponded === undefined ? item : { ...item, da_phan_hoi_het: allResponded }
            }),
          } : res)
          setUpdatedAt((res.lam_moi_luc && parseVietnamDate(res.lam_moi_luc)) || new Date())
          setError(null)
          setSelectedCaseId((prev) => {
            const valid = prev !== null && res.cases.some((c) => c.ca_id === prev)
            const nextId = valid ? prev : (res.cases[0]?.ca_id ?? null)
            saveSelectedCaseId(nextId)
            return nextId
          })
        })
        .catch((err: unknown) => {
          if (lifetime.signal.aborted) return
          if (background) console.warn('Làm mới danh sách y lệnh thất bại.')
          else setError(formatLoadError(err))
        })
        .finally(() => {
          inFlight = false
          if (feedbackDuringLoad.current === localFeedback) feedbackDuringLoad.current = null
          if (!lifetime.signal.aborted && !background) setLoading(false)
        })
    }

    loadRef.current = load
    load(false)
    const stop = watchForCaseRefresh(() => load(true), () => lastRequestAt)
    return () => {
      lifetime.abort()
      loadRef.current = null
      feedbackDuringLoad.current = null
      stop()
    }
  }, [client])

  const selectCase = useCallback((caId: string) => {
    setSelectedCaseId(caId)
    saveSelectedCaseId(caId)
  }, [])

  const setFilter = useCallback((nextFilter: QueueFilter) => {
    setFilterState(nextFilter)
    saveQueueFilter(nextFilter)
  }, [])

  const reload = useCallback(() => loadRef.current?.(false), [])
  const refresh = useCallback(() => loadRef.current?.(true), [])

  const markAllResponded = useCallback((caId: string, allResponded: boolean) => {
    feedbackDuringLoad.current?.set(caId, allResponded)
    setData((prev) => {
      if (!prev) {
        return prev
      }
      return {
        ...prev,
        cases: markCaseAllResponded(prev.cases, caId, allResponded),
      }
    })
  }, [])

  return {
    data,
    loading,
    error,
    selectedCaseId,
    filter,
    selectCase,
    setFilter,
    reload,
    refresh,
    updatedAt,
    markAllResponded,
  }
}
