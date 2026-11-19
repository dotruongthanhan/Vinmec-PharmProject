import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { requestCaseData, watchForCaseRefresh } from '../state/caseRefresh'

let visibility: EventTarget & { hidden: boolean }
let focus: EventTarget
let lastRequestAt: number
let stop: () => void

const start = () => {
  const refresh = vi.fn(() => { lastRequestAt = Date.now() })
  stop = watchForCaseRefresh(refresh, () => lastRequestAt)
  return refresh
}

beforeEach(() => {
  vi.useFakeTimers()
  lastRequestAt = Date.now()
  visibility = Object.assign(new EventTarget(), { hidden: false })
  focus = new EventTarget()
  vi.stubGlobal('document', visibility)
  vi.stubGlobal('window', focus)
})

afterEach(() => {
  stop?.()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('chu kỳ làm mới dữ liệu ca', () => {
  it('kết thúc GET bị treo sau một chu kỳ để lần làm mới sau còn chạy', async () => {
    const lifetime = new AbortController()
    const result = requestCaseData(lifetime.signal, (signal) => new Promise<void>((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(signal.reason), { once: true })
    }))
    const rejected = expect(result).rejects.toMatchObject({ name: 'AbortError' })
    await vi.advanceTimersByTimeAsync(60_000)
    await rejected
  })

  it('làm mới mỗi phút khi tab hiển thị và dọn bộ hẹn giờ khi rời trang', () => {
    const refresh = start()
    vi.advanceTimersByTime(59_999)
    expect(refresh).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(refresh).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(60_000)
    expect(refresh).toHaveBeenCalledTimes(2)
    stop()
    vi.advanceTimersByTime(120_000)
    expect(refresh).toHaveBeenCalledTimes(2)
  })

  it('tạm dừng khi ẩn, khi hiển thị lại chỉ làm mới một lần dù cũng nhận focus', () => {
    const refresh = start()
    visibility.hidden = true
    visibility.dispatchEvent(new Event('visibilitychange'))
    vi.advanceTimersByTime(120_000)
    focus.dispatchEvent(new Event('focus'))
    expect(refresh).not.toHaveBeenCalled()
    visibility.hidden = false
    visibility.dispatchEvent(new Event('visibilitychange'))
    focus.dispatchEvent(new Event('focus'))
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('focus sau hơn 30 giây làm mới ngay rồi bắt đầu lại nhịp 60 giây', () => {
    const refresh = start()
    vi.advanceTimersByTime(30_000)
    focus.dispatchEvent(new Event('focus'))
    expect(refresh).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    focus.dispatchEvent(new Event('focus'))
    expect(refresh).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(59_999)
    expect(refresh).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(1)
    expect(refresh).toHaveBeenCalledTimes(2)
  })
})
