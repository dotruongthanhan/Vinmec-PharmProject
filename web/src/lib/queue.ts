import type { DongHangDoi } from '../api/types.ts'

export type QueueFilter = 'tat_ca' | 'can_xem' | 'da_phan_hoi_het'

export interface QueueFilterOption {
  ma: QueueFilter
  nhan: string
}

export const QUEUE_FILTER_OPTIONS: readonly QueueFilterOption[] = [
  { ma: 'tat_ca', nhan: 'Tất cả' },
  { ma: 'can_xem', nhan: 'Cần xem' },
  { ma: 'da_phan_hoi_het', nhan: 'Đã phản hồi hết' },
]

/** Lọc danh sách hàng đợi theo bộ lọc, giữ nguyên thứ tự trả về từ API. */
export function filterQueue(
  cases: readonly DongHangDoi[],
  filter: QueueFilter,
): DongHangDoi[] {
  if (filter === 'can_xem') {
    return cases.filter((item) => item.uu_tien < 4)
  }
  if (filter === 'da_phan_hoi_het') {
    return cases.filter((item) => item.da_phan_hoi_het)
  }
  return [...cases]
}

/** Di chuyển lựa chọn ca lên hoặc xuống trong danh sách đang hiển thị. */
export function stepQueueSelection(
  cases: readonly DongHangDoi[],
  currentId: string | null,
  direction: 'up' | 'down',
): string | null {
  if (cases.length === 0) {
    return null
  }
  if (currentId === null) {
    return direction === 'up' ? cases[cases.length - 1].ca_id : cases[0].ca_id
  }
  const idx = cases.findIndex((item) => item.ca_id === currentId)
  if (idx === -1) {
    return cases[0].ca_id
  }
  const nextIdx =
    direction === 'down' ? Math.min(idx + 1, cases.length - 1) : Math.max(idx - 1, 0)
  return cases[nextIdx].ca_id
}

/** Cập nhật cờ đã phản hồi hết cho một ca trong hàng đợi mà không đổi thứ tự. */
export function markCaseAllResponded(
  cases: readonly DongHangDoi[],
  caId: string,
  allResponded: boolean,
): DongHangDoi[] {
  return cases.map((item) =>
    item.ca_id === caId ? { ...item, da_phan_hoi_het: allResponded } : item,
  )
}
