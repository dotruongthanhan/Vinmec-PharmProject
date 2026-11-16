import type { KetQuaAI, NhanDinh, PhanHoiDaGhi, TrangThaiAI } from '../api/types.ts'

export interface BangNhanDinh {
  can_chu_y: NhanDinh[]
  dat: NhanDinh[]
}

export interface AiSummaryCounts {
  coDienGiai: number
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

/** Đếm số nhận định có diễn giải/đề xuất AI và số nhận định mới do AI thêm. */
export function countAiSummary(ketQua: KetQuaAI | null): AiSummaryCounts {
  if (!ketQua?.nhan_dinh) {
    return { coDienGiai: 0, doAiThem: 0 }
  }
  const all = [...ketQua.nhan_dinh.can_chu_y, ...ketQua.nhan_dinh.dat]
  let coDienGiai = 0
  let doAiThem = 0

  for (const item of all) {
    if (hasNonEmptyText(item.dien_giai_ai) || hasNonEmptyText(item.de_xuat_ai)) {
      coDienGiai += 1
    }
    if (item.nguon_goc_ma !== 'luat' || item.nhan_dinh_id.startsWith('ai|')) {
      doAiThem += 1
    }
  }

  return { coDienGiai, doAiThem }
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
