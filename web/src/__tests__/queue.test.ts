import { describe, expect, it } from 'vitest'
import type { DongHangDoi } from '../api/types.ts'
import {
  filterQueue,
  markCaseAllResponded,
  stepQueueSelection,
} from '../lib/queue.ts'

const SAMPLE_QUEUE: DongHangDoi[] = [
  {
    ca_id: 'CA-Z',
    khoa: 'Hô hấp',
    mo_ta: 'Ca nghiêm trọng đầu tiên',
    uu_tien: 0,
    huy_hieu: '⛔ 1 nghiêm trọng',
    so_nghiem_trong: 1,
    so_can_luu_y: 0,
    so_thieu_du_lieu: 0,
    da_phan_hoi_het: false,
  },
  {
    ca_id: 'CA-A',
    khoa: 'Tim mạch',
    mo_ta: 'Ca cần lưu ý đã phản hồi hết',
    uu_tien: 1,
    huy_hieu: '⚠ 1 cần lưu ý',
    so_nghiem_trong: 0,
    so_can_luu_y: 1,
    so_thieu_du_lieu: 0,
    da_phan_hoi_het: true,
  },
  {
    ca_id: 'CA-M',
    khoa: 'Nội tiết',
    mo_ta: 'Ca đạt',
    uu_tien: 4,
    huy_hieu: '✓ Đạt',
    so_nghiem_trong: 0,
    so_can_luu_y: 0,
    so_thieu_du_lieu: 0,
    da_phan_hoi_het: false,
  },
  {
    ca_id: 'CA-B',
    khoa: 'Tai mũi họng',
    mo_ta: 'Ca thiếu dữ liệu',
    uu_tien: 3,
    huy_hieu: '? 1 thiếu dữ liệu',
    so_nghiem_trong: 0,
    so_can_luu_y: 0,
    so_thieu_du_lieu: 1,
    da_phan_hoi_het: true,
  },
]

describe('filterQueue', () => {
  it('lọc tất cả giữ nguyên đúng thứ tự từ API', () => {
    const result = filterQueue(SAMPLE_QUEUE, 'tat_ca')
    expect(result.map((c) => c.ca_id)).toEqual(['CA-Z', 'CA-A', 'CA-M', 'CA-B'])
  })

  it('lọc cần xem chỉ lấy ca uu_tien < 4 và giữ nguyên thứ tự', () => {
    const result = filterQueue(SAMPLE_QUEUE, 'can_xem')
    expect(result.map((c) => c.ca_id)).toEqual(['CA-Z', 'CA-A', 'CA-B'])
  })

  it('lọc đã phản hồi hết chỉ lấy ca da_phan_hoi_het = true và giữ nguyên thứ tự', () => {
    const result = filterQueue(SAMPLE_QUEUE, 'da_phan_hoi_het')
    expect(result.map((c) => c.ca_id)).toEqual(['CA-A', 'CA-B'])
  })
})

describe('stepQueueSelection và markCaseAllResponded', () => {
  it('di chuyển chọn ca lên xuống đúng ranh giới', () => {
    expect(stepQueueSelection(SAMPLE_QUEUE, 'CA-Z', 'down')).toBe('CA-A')
    expect(stepQueueSelection(SAMPLE_QUEUE, 'CA-Z', 'up')).toBe('CA-Z')
    expect(stepQueueSelection(SAMPLE_QUEUE, 'CA-B', 'down')).toBe('CA-B')
    expect(stepQueueSelection(SAMPLE_QUEUE, 'CA-B', 'up')).toBe('CA-M')
    expect(stepQueueSelection([], 'CA-Z', 'down')).toBeNull()
  })

  it('cập nhật da_phan_hoi_het cho đúng ca mà không thay đổi thứ tự', () => {
    const updated = markCaseAllResponded(SAMPLE_QUEUE, 'CA-Z', true)
    expect(updated.map((c) => c.ca_id)).toEqual(['CA-Z', 'CA-A', 'CA-M', 'CA-B'])
    expect(updated[0].da_phan_hoi_het).toBe(true)
    expect(SAMPLE_QUEUE[0].da_phan_hoi_het).toBe(false)
  })
})
