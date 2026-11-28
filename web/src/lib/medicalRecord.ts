import type { ChiTietCa, MedicalOrder } from '@/api/types'
import type { EncounterGroup } from './uiTypes'
import { extractOrderCode } from './displayFormat'

/** Tương thích dữ liệu demo cũ không có danh sách y lệnh. */
export function medicalOrders(detail: ChiTietCa): MedicalOrder[] {
  if (detail.danh_sach_y_lenh) return detail.danh_sach_y_lenh
  const orders = detail.chi_tiet.y_lenh
  const result: MedicalOrder[] = [{
    y_lenh_id: extractOrderCode(orders.thong_tin_text, detail.ca_id),
    dot_dieu_tri_id: detail.quan_ly_nguoi_benh?.dot_dieu_tri_id ?? `DT-${detail.ca_id}`,
    thu_tu_dot: 1, la_trong_tam: true, trang_thai: 'cho_duyet', ...orders.cho_duyet,
  }]
  if (orders.dang_dung?.dong.length) result.push({
    y_lenh_id: `YL-${detail.ca_id}-NEN`, dot_dieu_tri_id: result[0].dot_dieu_tri_id,
    thu_tu_dot: 1, la_trong_tam: false, trang_thai: 'dang_thuc_hien', ...orders.dang_dung,
  })
  return result
}

/** Đếm y lệnh của mọi lần vào viện, bỏ mục thuốc nền giả lập. */
export function countMedicalOrders(orders: readonly MedicalOrder[], caId: string): number {
  return orders.filter((order) => order.la_trong_tam || order.y_lenh_id !== `YL-${caId}-NEN`).length
}

/** URL sai hoặc thuộc ca trước quay về y lệnh trọng tâm. */
export function selectMedicalOrder(orders: readonly MedicalOrder[], requested: string | null): MedicalOrder | undefined {
  return orders.find((order) => order.y_lenh_id === requested)
    ?? orders.find((order) => order.la_trong_tam) ?? orders[0]
}

/** Giữ các tham số khác và mã hoá mã y lệnh bằng URLSearchParams. */
export function orderSelectionParams(previous: URLSearchParams, id: string): URLSearchParams {
  const next = new URLSearchParams(previous)
  next.set('tab', 'y_lenh')
  next.set('yl', id)
  return next
}

/** Nhóm theo mã đợt, thứ tự hiển thị theo lần vào viện. */
export function groupEncounters<T extends { dot_dieu_tri_id: string; thu_tu_dot?: number | null }>(items: readonly T[]): EncounterGroup<T>[] {
  const groups = new Map<string, EncounterGroup<T>>()
  for (const item of items) {
    const group = groups.get(item.dot_dieu_tri_id) ?? {
      id: item.dot_dieu_tri_id, thuTu: item.thu_tu_dot ?? null, items: [],
    }
    group.items.push(item)
    groups.set(group.id, group)
  }
  return [...groups.values()].sort((a, b) => (a.thuTu ?? 0) - (b.thuTu ?? 0))
}
