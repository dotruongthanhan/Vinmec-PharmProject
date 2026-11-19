import type { KetQuaAI, NhanDinh, PhanHoiDaGhi, TrangThaiAI } from '../api/types.ts'

export interface BangNhanDinh {
  can_chu_y: NhanDinh[]
  dat: NhanDinh[]
}

export interface AiSummaryCounts {
  coDienGiai: number
  coDienGiaiCanChuY: number
  coDienGiaiDat: number
  doAiThem: number
}

export interface HighlightSegment {
  text: string
  highlighted: boolean
}

const SAFE_HTTPS_PREFIX = ['ht', 'tps://'].join('')

function hasNonEmptyText(value: string | null | undefined): boolean {
  return typeof value === 'string' && value.trim() !== ''
}

/** Chọn bảng nhận định hiển thị: dùng kết quả AI khi đã xong và có nhan_dinh, ngược lại dùng bảng của luật. */
export function selectFindingsSource(
  ruleFindings: BangNhanDinh,
  trangThai: TrangThaiAI,
  ketQua: KetQuaAI | null,
): BangNhanDinh {
  if (trangThai === 'xong' && ketQua?.nhan_dinh) {
    return ketQua.nhan_dinh
  }
  return ruleFindings
}

/** Giữ nguyên trạng thái phản hồi của từng thẻ khi chuyển đổi giữa bảng luật và bảng AI theo nhan_dinh_id. */
export function mergeFindingsFeedback(
  findings: BangNhanDinh,
  feedbackById: Readonly<Record<string, PhanHoiDaGhi>>,
  fallbackSources: readonly BangNhanDinh[] = [],
): BangNhanDinh {
  const fallbackMap = new Map<string, PhanHoiDaGhi>()
  for (const src of fallbackSources) {
    for (const item of src.can_chu_y) {
      if (item.phan_hoi !== null) {
        fallbackMap.set(item.nhan_dinh_id, item.phan_hoi)
      }
    }
    for (const item of src.dat) {
      if (item.phan_hoi !== null) {
        fallbackMap.set(item.nhan_dinh_id, item.phan_hoi)
      }
    }
  }

  const applyList = (list: readonly NhanDinh[]): NhanDinh[] =>
    list.map((item) => {
      const resolved =
        feedbackById[item.nhan_dinh_id] ??
        item.phan_hoi ??
        fallbackMap.get(item.nhan_dinh_id) ??
        null
      return resolved === item.phan_hoi ? item : { ...item, phan_hoi: resolved }
    })

  return {
    can_chu_y: applyList(findings.can_chu_y),
    dat: applyList(findings.dat),
  }
}

function hasAiExplanation(item: NhanDinh): boolean {
  return hasNonEmptyText(item.dien_giai_ai) || hasNonEmptyText(item.de_xuat_ai)
}

function isAddedByAi(item: NhanDinh): boolean {
  return item.nguon_goc_ma !== 'luat' || item.nhan_dinh_id.startsWith('ai|')
}

/** Đếm số nhận định có diễn giải/đề xuất AI (tổng và theo nhóm) cùng số nhận định mới do AI thêm. */
export function countAiSummary(ketQua: KetQuaAI | null): AiSummaryCounts {
  if (!ketQua?.nhan_dinh) {
    return { coDienGiai: 0, coDienGiaiCanChuY: 0, coDienGiaiDat: 0, doAiThem: 0 }
  }
  let coDienGiaiCanChuY = 0
  let coDienGiaiDat = 0
  let doAiThem = 0

  for (const item of ketQua.nhan_dinh.can_chu_y) {
    if (hasAiExplanation(item)) {
      coDienGiaiCanChuY += 1
    }
    if (isAddedByAi(item)) {
      doAiThem += 1
    }
  }

  for (const item of ketQua.nhan_dinh.dat) {
    if (hasAiExplanation(item)) {
      coDienGiaiDat += 1
    }
    if (isAddedByAi(item)) {
      doAiThem += 1
    }
  }

  return {
    coDienGiai: coDienGiaiCanChuY + coDienGiaiDat,
    coDienGiaiCanChuY,
    coDienGiaiDat,
    doAiThem,
  }
}

/** Tạo câu tóm tắt trên thanh trạng thái AI khi hoàn tất, ghi rõ số diễn giải theo nhóm (bỏ nhóm bằng 0). */
export function formatAiDoneMessage(
  thoiGianMs: number | null,
  summary: Pick<AiSummaryCounts, 'coDienGiai' | 'doAiThem'> & {
    coDienGiaiCanChuY?: number
    coDienGiaiDat?: number
  },
): string {
  const timeText = thoiGianMs !== null ? ` (${formatAiSeconds(thoiGianMs)} giây)` : ''
  const parts: string[] = []
  if ((summary.coDienGiaiCanChuY ?? 0) > 0) {
    parts.push(`${summary.coDienGiaiCanChuY} cần chú ý`)
  }
  if ((summary.coDienGiaiDat ?? 0) > 0) {
    parts.push(`${summary.coDienGiaiDat} đạt`)
  }
  const breakdown = parts.length > 0 ? ` (${parts.join(', ')})` : ''
  return `AI đã phân tích xong${timeText}. ${summary.coDienGiai} nhận định có diễn giải${breakdown}, ${summary.doAiThem} nhận định do AI thêm.`
}

/** Tách văn bản nguồn bằng indexOf để tô nền đoạn trùng khớp trích dẫn. */
export function splitHighlightSegments(
  noiDung: string,
  trichNguyenVan: string,
): HighlightSegment[] {
  if (!noiDung || !trichNguyenVan || trichNguyenVan.trim() === '') {
    return [{ text: noiDung, highlighted: false }]
  }
  const idx = noiDung.indexOf(trichNguyenVan)
  if (idx === -1) {
    return [{ text: noiDung, highlighted: false }]
  }

  const segments: HighlightSegment[] = []
  if (idx > 0) {
    segments.push({ text: noiDung.slice(0, idx), highlighted: false })
  }
  const endIdx = idx + trichNguyenVan.length
  segments.push({ text: noiDung.slice(idx, endIdx), highlighted: true })
  if (endIdx < noiDung.length) {
    segments.push({ text: noiDung.slice(endIdx), highlighted: false })
  }
  return segments
}

/** Trả về URL đã cắt khoảng trắng nếu bắt đầu bằng giao thức HTTPS an toàn, ngược lại trả null. */
export function getSafeHttpsUrl(url: string | null | undefined): string | null {
  if (typeof url !== 'string') {
    return null
  }
  const trimmed = url.trim()
  if (!trimmed.startsWith(SAFE_HTTPS_PREFIX) || trimmed.length <= SAFE_HTTPS_PREFIX.length) {
    return null
  }
  return trimmed
}

/** Định dạng mili-giây sang giây dùng dấu phẩy thập phân để hiển thị trên dải trạng thái AI. */
export function formatAiSeconds(ms: number): string {
  return (Math.max(0, ms) / 1000).toFixed(1).replace(/\.0$/, '').replace('.', ',')
}
