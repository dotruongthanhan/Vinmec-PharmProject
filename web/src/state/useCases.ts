import { useCallback, useEffect, useState } from 'react'
import type { ReviewApiClient } from '../api/client.ts'
import type { DanhSachCa } from '../api/types.ts'
import { loadUiPrefs, saveQueueFilter, saveSelectedCaseId } from '../lib/prefs.ts'
import { markCaseAllResponded } from '../lib/queue.ts'
import type { QueueFilter } from '../lib/queue.ts'

export interface UseCasesResult {
  data: DanhSachCa | null
  loading: boolean
  error: string | null
  selectedCaseId: string | null
  filter: QueueFilter
  selectCase: (caId: string) => void
  setFilter: (filter: QueueFilter) => void
  reload: () => void
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
  const [reloadCount, setReloadCount] = useState<number>(0)

  useEffect(() => {
    let cancelled = false

    client
      .getCases()
      .then((res) => {
        if (cancelled) {
          return
        }
        setData(res)
        setError(null)
        setSelectedCaseId((prev) => {
          const valid = prev !== null && res.cases.some((c) => c.ca_id === prev)
          const nextId = valid ? prev : (res.cases[0]?.ca_id ?? null)
          saveSelectedCaseId(nextId)
          return nextId
        })
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        setError(formatLoadError(err))
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [client, reloadCount])

  const selectCase = useCallback((caId: string) => {
    setSelectedCaseId(caId)
    saveSelectedCaseId(caId)
  }, [])

  const setFilter = useCallback((nextFilter: QueueFilter) => {
    setFilterState(nextFilter)
    saveQueueFilter(nextFilter)
  }, [])

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    setReloadCount((n) => n + 1)
  }, [])

  const markAllResponded = useCallback((caId: string, allResponded: boolean) => {
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
    markAllResponded,
  }
}
