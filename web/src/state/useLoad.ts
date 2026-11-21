import { useCallback, useEffect, useState } from 'react'

export interface LoadState<T> {
  data: T | null
  loading: boolean
  error: string | null
  /** Mã HTTP khi lỗi do ApiError (404 để trang chi tiết hiện "không tìm thấy"). */
  status: number | null
  reload: () => void
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/** Tải dữ liệu một lần theo `key`, huỷ yêu cầu cũ khi key đổi hoặc rời trang. */
export function useLoad<T>(
  load: (signal: AbortSignal) => Promise<T>,
  key: string,
  fallbackError: string,
): LoadState<T> {
  const [state, setState] = useState<{ key: string; data: T | null; error: string | null; status: number | null; done: boolean }>(
    { key, data: null, error: null, status: null, done: false },
  )
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setState({ key, data, error: null, status: null, done: true })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        const status = typeof (err as { status?: unknown })?.status === 'number' ? (err as { status: number }).status : null
        setState({ key, data: null, error: errorMessage(err, fallbackError), status, done: true })
      })
    return () => controller.abort()
    // `load` đổi theo key đã được phản ánh bằng `key` và `nonce`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce])

  const reload = useCallback(() => {
    setState((prev) => ({ ...prev, done: false }))
    setNonce((n) => n + 1)
  }, [])

  const current = state.key === key
  return {
    data: current ? state.data : null,
    loading: !current || !state.done,
    error: current ? state.error : null,
    status: current ? state.status : null,
    reload,
  }
}
