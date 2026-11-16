import { useCallback, useState } from 'react'
import type { ReviewApiClient } from '../api/client.ts'
import type { GuiPhanHoi, PhanHoiDaGhi } from '../api/types.ts'

export interface UseFeedbackResult {
  isSubmitting: (caId: string, nhanDinhId: string) => boolean
  getError: (caId: string, nhanDinhId: string) => string | null
  clearError: (caId: string, nhanDinhId: string) => void
  submitFeedback: (caId: string, payload: GuiPhanHoi) => Promise<boolean>
}

function makeKey(caId: string, nhanDinhId: string): string {
  return `${caId}::${nhanDinhId}`
}

function formatFeedbackError(err: unknown): string {
  if (err instanceof Error && err.message) {
    return err.message
  }
  return 'Không ghi được phản hồi. Vui lòng thử lại.'
}

/** Điều phối gửi phản hồi từng nhận định, giữ nguyên nội dung khi có lỗi. */
export function useFeedback(
  client: ReviewApiClient,
  onSuccess: (caId: string, nhanDinhId: string, recorded: PhanHoiDaGhi) => void,
): UseFeedbackResult {
  const [submittingMap, setSubmittingMap] = useState<Record<string, boolean>>({})
  const [errorMap, setErrorMap] = useState<Record<string, string>>({})

  const isSubmitting = useCallback(
    (caId: string, nhanDinhId: string): boolean => Boolean(submittingMap[makeKey(caId, nhanDinhId)]),
    [submittingMap],
  )

  const getError = useCallback(
    (caId: string, nhanDinhId: string): string | null =>
      errorMap[makeKey(caId, nhanDinhId)] ?? null,
    [errorMap],
  )

  const clearError = useCallback((caId: string, nhanDinhId: string) => {
    const key = makeKey(caId, nhanDinhId)
    setErrorMap((prev) => {
      if (!(key in prev)) {
        return prev
      }
      const next = { ...prev }
      delete next[key]
      return next
    })
  }, [])

  const submitFeedback = useCallback(
    async (caId: string, payload: GuiPhanHoi): Promise<boolean> => {
      const key = makeKey(caId, payload.nhan_dinh_id)
      setSubmittingMap((prev) => ({ ...prev, [key]: true }))
      setErrorMap((prev) => {
        if (!(key in prev)) {
          return prev
        }
        const next = { ...prev }
        delete next[key]
        return next
      })

      try {
        const recorded = await client.sendFeedback(caId, payload)
        onSuccess(caId, payload.nhan_dinh_id, recorded)
        setSubmittingMap((prev) => ({ ...prev, [key]: false }))
        return true
      } catch (err: unknown) {
        setErrorMap((prev) => ({ ...prev, [key]: formatFeedbackError(err) }))
        setSubmittingMap((prev) => ({ ...prev, [key]: false }))
        return false
      }
    },
    [client, onSuccess],
  )

  return {
    isSubmitting,
    getError,
    clearError,
    submitFeedback,
  }
}
