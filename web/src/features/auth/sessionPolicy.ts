import { getSessionTimestampStorage, SESSION_POLICY_KEY } from '@/lib/demoSession'
import type { SessionTimestampStorage } from '@/lib/demoSession'

export const IDLE_LIMIT_MS = 30 * 60_000
export const MAX_SESSION_MS = 12 * 60 * 60_000
const ACTIVITY_THROTTLE_MS = 5_000
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const

export type SessionExpiryReason = 'khong_hoat_dong' | 'het_han_phien'

export interface SessionClock {
  now(): number
  setTimeout(callback: () => void, delay: number): ReturnType<typeof setTimeout>
  clearTimeout(timer: ReturnType<typeof setTimeout>): void
}

export const systemSessionClock: SessionClock = {
  now: () => Date.now(),
  setTimeout: (callback, delay) => setTimeout(callback, delay),
  clearTimeout: (timer) => clearTimeout(timer),
}

interface PolicyOptions {
  identity: string
  onExpire(reason: SessionExpiryReason): void
  clock?: SessionClock
  storage?: SessionTimestampStorage
  target?: Pick<EventTarget, 'addEventListener' | 'removeEventListener'>
}

/** Giữ hạn nhàn rỗi và hạn tuyệt đối qua lần tải lại trong cùng thẻ. */
export function startSessionPolicy({ identity, onExpire, clock = systemSessionClock,
  storage = getSessionTimestampStorage(), target = typeof window === 'undefined' ? undefined : window }: PolicyOptions): () => void {
  const now = clock.now()
  let startedAt = now
  let lastActivityAt = now
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    const saved = JSON.parse(storage?.getItem(SESSION_POLICY_KEY) ?? 'null') as unknown
    if (saved && typeof saved === 'object' && 'identity' in saved && saved.identity === identity
      && 'startedAt' in saved && typeof saved.startedAt === 'number' && Number.isFinite(saved.startedAt)
      && 'lastActivityAt' in saved && typeof saved.lastActivityAt === 'number' && Number.isFinite(saved.lastActivityAt)
      && saved.startedAt <= saved.lastActivityAt && saved.lastActivityAt <= now) {
      startedAt = saved.startedAt
      lastActivityAt = saved.lastActivityAt
    }
  } catch {
    // Bộ nhớ không hợp lệ không ngăn khởi động bộ hạn giờ.
  }
  const save = () => {
    try {
      storage?.setItem(SESSION_POLICY_KEY, JSON.stringify({ identity, startedAt, lastActivityAt }))
    } catch {
      // Khi bộ nhớ bị chặn, giữ mốc trong bộ nhớ ứng dụng.
    }
  }
  const stop = () => {
    stopped = true
    if (timer !== undefined) clock.clearTimeout(timer)
    for (const event of ACTIVITY_EVENTS) target?.removeEventListener(event, activity)
  }
  const check = (): boolean => {
    const current = clock.now()
    const reason = current - startedAt >= MAX_SESSION_MS ? 'het_han_phien'
      : current - lastActivityAt >= IDLE_LIMIT_MS ? 'khong_hoat_dong' : null
    if (reason) {
      stop()
      onExpire(reason)
      return true
    }
    return false
  }
  const schedule = () => {
    if (timer !== undefined) clock.clearTimeout(timer)
    timer = clock.setTimeout(() => { if (!stopped && !check()) schedule() },
      Math.max(0, Math.min(startedAt + MAX_SESSION_MS, lastActivityAt + IDLE_LIMIT_MS) - clock.now()))
  }
  function activity() {
    if (stopped || check()) return
    const current = clock.now()
    if (current - lastActivityAt < ACTIVITY_THROTTLE_MS) return
    lastActivityAt = current
    save()
    schedule()
  }
  save()
  for (const event of ACTIVITY_EVENTS) target?.addEventListener(event, activity, { passive: true })
  schedule()
  return stop
}
