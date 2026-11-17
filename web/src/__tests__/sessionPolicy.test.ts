import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startSessionPolicy } from '../features/auth/sessionPolicy'

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(1_000_000) })
afterEach(() => { vi.useRealTimers() })

function setup() {
  const records = new Map<string, string>()
  const storage = {
    getItem: (key: string) => records.get(key) ?? null,
    setItem: vi.fn((key: string, value: string) => { records.set(key, value) }),
    removeItem: (key: string) => { records.delete(key) },
  }
  const target = new EventTarget()
  const expired = vi.fn()
  const start = (identity = 'tai-khoan:phien') => startSessionPolicy({ identity, storage, target, onExpire: expired })
  return { storage, target, expired, start }
}

describe('chính sách thời gian phiên', () => {
  it('đúng 30 phút nhàn rỗi đăng xuất và dọn bộ hẹn giờ', () => {
    const app = setup()
    const stop = app.start()
    vi.advanceTimersByTime(1_799_999)
    expect(app.expired).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(app.expired).toHaveBeenCalledExactlyOnceWith('khong_hoat_dong')
    stop()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('hoạt động đặt lại hạn nhàn rỗi, giới hạn ghi một lần mỗi 5 giây', () => {
    const app = setup()
    const stop = app.start()
    vi.advanceTimersByTime(600_000)
    app.target.dispatchEvent(new Event('keydown'))
    const writes = app.storage.setItem.mock.calls.length
    vi.advanceTimersByTime(1_000)
    for (const event of ['pointerdown', 'wheel', 'touchstart']) app.target.dispatchEvent(new Event(event))
    expect(app.storage.setItem).toHaveBeenCalledTimes(writes)
    vi.advanceTimersByTime(1_799_000)
    expect(app.expired).toHaveBeenCalledExactlyOnceWith('khong_hoat_dong')
    stop()
  })

  it('hoạt động đều không kéo dài phiên quá 12 giờ', () => {
    const app = setup()
    const stop = app.start()
    for (let hour = 0; hour < 47; hour += 1) {
      vi.advanceTimersByTime(900_000)
      app.target.dispatchEvent(new Event('pointerdown'))
    }
    expect(app.expired).not.toHaveBeenCalled()
    vi.advanceTimersByTime(900_000)
    expect(app.expired).toHaveBeenCalledExactlyOnceWith('het_han_phien')
    stop()
  })

  it('tải lại giữ mốc thời gian cùng phiên; phiên mới bắt đầu lại', () => {
    const app = setup()
    let stop = app.start()
    vi.advanceTimersByTime(1_200_000)
    stop()
    stop = app.start()
    vi.advanceTimersByTime(600_000)
    expect(app.expired).toHaveBeenCalledExactlyOnceWith('khong_hoat_dong')
    stop()
    app.expired.mockClear()
    stop = app.start('tai-khoan-khac:phien-moi')
    vi.advanceTimersByTime(1_799_999)
    expect(app.expired).not.toHaveBeenCalled()
    stop()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('sự kiện sau khi dọn không tạo lại hẹn giờ hoặc ghi bộ nhớ', () => {
    const app = setup()
    const stop = app.start()
    stop()
    const writes = app.storage.setItem.mock.calls.length
    vi.advanceTimersByTime(10_000)
    app.target.dispatchEvent(new Event('keydown'))
    expect(app.storage.setItem).toHaveBeenCalledTimes(writes)
    expect(vi.getTimerCount()).toBe(0)
  })
})
