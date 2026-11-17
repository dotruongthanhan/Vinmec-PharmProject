import type { ChiTietCa, DienBienTomTat, NhanDinh } from '../api/types.ts'

export type SixFactorStatus = 'co_van_de' | 'dat' | 'thieu_du_lieu' | 'chua_co_luat'

export interface SixFactorItem {
  index: 1 | 2 | 3 | 4 | 5 | 6 | 7
  title: string
  status: SixFactorStatus
  statusLabel: string
  firstFindingId: string | null
  inPassedOnly: boolean
}

/** Bảy yếu tố thẩm định theo đúng đánh số của backend (tên biến giữ "six" để không đổi chỗ gọi). */
export const SIX_FACTOR_DEFINITIONS: readonly {
  index: 1 | 2 | 3 | 4 | 5 | 6 | 7
  title: string
}[] = [
  { index: 1, title: 'Dị ứng, quá mẫn' },
  { index: 2, title: 'Trùng lặp thuốc' },
  { index: 3, title: 'Chỉ định, liều, đường dùng' },
  { index: 4, title: 'Tương tác thuốc' },
  { index: 5, title: 'Độc tính' },
  { index: 6, title: 'Cơ địa và xét nghiệm' },
  { index: 7, title: 'Lịch dùng và yếu tố khác' },
]

export const SIX_FACTOR_STATUS_LABELS: Record<SixFactorStatus, string> = {
  co_van_de: 'Có vấn đề',
  dat: 'Đạt',
  thieu_du_lieu: 'Thiếu dữ liệu',
  chua_co_luat: 'Chưa có luật',
}

function matchesFactorIndex(yeuToText: string, index: number): boolean {
  const trimmed = yeuToText.trim()
  return trimmed.startsWith(`${index}.`) || trimmed.startsWith(`${index} ·`)
}

/**
 * Quyết định trạng thái của sáu yếu tố thẩm định:
 * - Yếu tố có nhận định cần xem / ngoài HDSD → `co_van_de`
 * - Yếu tố có nhận định không đủ dữ liệu → `thieu_du_lieu`
 * - Yếu tố nằm trong danh sách chưa kiểm hoặc không có luật chạy → `chua_co_luat` (không bao giờ ra `dat`)
 * - Yếu tố đã chạy luật và tất cả đạt → `dat`
 */
export function computeSixFactorsStatus(
  nhanDinh: Pick<ChiTietCa['nhan_dinh'], 'can_chu_y' | 'dat' | 'yeu_to_chua_kiem'>,
): SixFactorItem[] {
  return SIX_FACTOR_DEFINITIONS.map((def) => {
    const attention = nhanDinh.can_chu_y.filter((item) => matchesFactorIndex(item.yeu_to, def.index))
    const passed = nhanDinh.dat.filter((item) => matchesFactorIndex(item.yeu_to, def.index))
    const isMarkedUntested = nhanDinh.yeu_to_chua_kiem.some((label) =>
      matchesFactorIndex(label, def.index),
    )

    let status: SixFactorStatus = 'chua_co_luat'
    let firstFindingId: string | null = null
    let inPassedOnly = false

    const problemFinding = attention.find(
      (item) => item.ket_luan_ma === 'can_xem' || item.ket_luan_ma === 'ngoai_hdsd',
    )
    const missingFinding = attention.find((item) => item.ket_luan_ma === 'khong_du_du_lieu')

    if (problemFinding) {
      status = 'co_van_de'
      firstFindingId = problemFinding.nhan_dinh_id
    } else if (missingFinding) {
      status = 'thieu_du_lieu'
      firstFindingId = missingFinding.nhan_dinh_id
    } else if (isMarkedUntested) {
      status = 'chua_co_luat'
    } else if (passed.length > 0) {
      status = 'dat'
      firstFindingId = passed[0].nhan_dinh_id
      inPassedOnly = true
    } else {
      status = 'chua_co_luat'
    }

    return {
      index: def.index,
      title: def.title,
      status,
      statusLabel: SIX_FACTOR_STATUS_LABELS[status],
      firstFindingId,
      inPassedOnly,
    }
  })
}

/** Lọc danh sách nhận định theo tên thuốc được bấm ở bảng Y lệnh; không chọn thuốc thì giữ nguyên toàn bộ. */
export function filterFindingsByDrug(
  findings: readonly NhanDinh[],
  selectedDrug: string | null,
): NhanDinh[] {
  if (!selectedDrug) {
    return [...findings]
  }
  const needle = selectedDrug.trim().toLowerCase()
  if (!needle) {
    return [...findings]
  }
  return findings.filter((item) => item.thuoc.toLowerCase().includes(needle))
}

/** Bỏ câu "Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức" khi thẻ đã có trích dẫn nguồn thật. */
export function stripPendingSourceNote(
  ghiChu: string | null,
  hasCitations: boolean,
): string | null {
  if (!ghiChu) {
    return null
  }
  if (!hasCitations) {
    return ghiChu
  }
  const cleaned = ghiChu
    .replace(/Nguyên văn đoạn nguồn sẽ có khi nối kho tri thức\.?/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned || null
}

/** Rút gọn tên thuốc từ chuỗi đầy đủ để gợi ý câu hỏi ngắn gọn. */
export function extractShortDrugName(thuoc: string): string {
  const firstSegment = thuoc.split('–')[0]?.split('·')[0]?.trim() ?? ''
  return firstSegment || thuoc.trim()
}

/** Chuẩn hoá chuỗi nhãn hồ sơ để nhận diện phiếu điều trị một cách nhất quán. */
export function isTreatmentSheetNote(note: Pick<DienBienTomTat, 'loai_nhan'>): boolean {
  const normalized = note.loai_nhan
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/gi, 'd')
    .trim()
    .toLowerCase()
  return normalized.includes('phieu dieu tri')
}

/** Lọc riêng các bản ghi phiếu điều trị từ danh sách diễn biến của ca bệnh. */
export function filterTreatmentSheetNotes(
  notes: readonly DienBienTomTat[],
): DienBienTomTat[] {
  return notes.filter((note) => isTreatmentSheetNote(note))
}
