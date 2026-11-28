import { parseVietnamDate, VIETNAM_TIME_ZONE } from './displayFormat'

/** Giờ hỏi gần nhất của một hội thoại; trả chuỗi rỗng nếu không rõ. */
export function formatHistoryTime(iso: string | null): string {
  if (!iso) {
    return ''
  }
  const date = parseVietnamDate(iso)
  if (!date) {
    return ''
  }
  return date.toLocaleString('vi-VN', {
    timeZone: VIETNAM_TIME_ZONE,
    hourCycle: 'h23',
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  })
}
