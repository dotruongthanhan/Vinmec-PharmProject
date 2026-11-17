/** Giờ hỏi gần nhất của một hội thoại, dạng hh:mm dd/mm; trả chuỗi rỗng nếu không rõ. */
export function formatHistoryTime(iso: string | null): string {
  if (!iso) {
    return ''
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  })
}
