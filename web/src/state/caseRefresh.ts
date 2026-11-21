const REFRESH_INTERVAL_MS = 60_000
const RESUME_AFTER_MS = 30_000

/** Huỷ GET khi rời màn hình hoặc quá một chu kỳ, để có thể thử lại. */
export async function requestCaseData<T>(
  lifetime: AbortSignal,
  request: (signal: AbortSignal) => Promise<T>,
): Promise<T> {
  lifetime.throwIfAborted()
  const controller = new AbortController()
  const abort = () => controller.abort()
  lifetime.addEventListener('abort', abort, { once: true })
  const deadline = setTimeout(abort, REFRESH_INTERVAL_MS)
  try {
    const data = await request(controller.signal)
    controller.signal.throwIfAborted()
    return data
  } finally {
    clearTimeout(deadline)
    lifetime.removeEventListener('abort', abort)
  }
}

/** Làm mới theo lần yêu cầu gần nhất, chỉ khi tab đang hiển thị. */
export function watchForCaseRefresh(refresh: () => void, lastRequestAt: () => number): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined
  const remaining = () => REFRESH_INTERVAL_MS - (Date.now() - lastRequestAt())

  const schedule = (delay: number) => {
    clearTimeout(timer)
    if (!document.hidden) timer = setTimeout(tick, Math.max(0, delay))
  }

  function tick() {
    if (document.hidden) return
    const delay = remaining()
    if (delay <= 0) refresh()
    schedule(delay > 0 ? delay : REFRESH_INTERVAL_MS)
  }

  const resume = () => {
    if (!document.hidden && Date.now() - lastRequestAt() > RESUME_AFTER_MS) refresh()
    schedule(remaining())
  }

  schedule(remaining())
  document.addEventListener('visibilitychange', resume)
  window.addEventListener('focus', resume)
  return () => {
    clearTimeout(timer)
    document.removeEventListener('visibilitychange', resume)
    window.removeEventListener('focus', resume)
  }
}
