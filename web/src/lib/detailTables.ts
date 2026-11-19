import type { BangYLenh, ChiTietXetNghiemDong, MaTranTuongTac, NhanDinh, TuongTacThucAn } from '../api/types.ts'
import { formatClinicalText, parseTrendValue } from './displayFormat.ts'
import type { TrendDirection } from './displayFormat.ts'

/* ---------- Dòng thông tin dạng "nhãn: giá trị" ---------- */

export interface InfoPair {
  label: string
  value: string
}

/** Tách chuỗi "Mã y lệnh: A · Khoa kê: B" thành các cặp nhãn – giá trị. */
export function parseInfoPairs(text: string): InfoPair[] {
  return text
    .split('·')
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const idx = part.indexOf(':')
      if (idx < 0) {
        return { label: '', value: part }
      }
      return { label: part.slice(0, idx).trim(), value: part.slice(idx + 1).trim() }
    })
}

/* ---------- Lịch dùng của một dòng thuốc ---------- */

export interface ScheduleDose {
  date: string
  time: string
  dose: string
}

export interface ScheduleDay {
  date: string
  doses: ScheduleDose[]
}

const DOSE_PATTERN = /(\d{2}\/\d{2}\/\d{4})\s+(\d{2}:\d{2})(?:\s*\(([^)]*)\))?/g

/** Tách cột "Lịch dùng" thành từng mốc dùng thuốc; chuỗi không đúng dạng thì trả mảng rỗng. */
export function parseSchedule(raw: string): ScheduleDose[] {
  const doses: ScheduleDose[] = []
  for (const match of raw.matchAll(DOSE_PATTERN)) {
    doses.push({ date: match[1], time: match[2], dose: (match[3] ?? '').trim() })
  }
  return doses
}

/** Gom các mốc dùng thuốc theo ngày, giữ thứ tự xuất hiện. */
export function groupScheduleByDay(doses: readonly ScheduleDose[]): ScheduleDay[] {
  const days: ScheduleDay[] = []
  for (const dose of doses) {
    const last = days[days.length - 1]
    if (last && last.date === dose.date) {
      last.doses.push(dose)
    } else {
      days.push({ date: dose.date, doses: [dose] })
    }
  }
  return days
}

/* ---------- Bảng xét nghiệm xoay ngang theo thời điểm ---------- */

export interface LabPivotCell {
  text: string
  abnormal: boolean
  direction: TrendDirection | null
}

export interface LabPivotRow {
  name: string
  unit: string
  reference: string
  cells: (LabPivotCell | null)[]
  hasAbnormal: boolean
}

export interface LabPivot {
  times: string[]
  rows: LabPivotRow[]
}

function timeSortKey(text: string): string {
  const match = /(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})/.exec(text)
  if (!match) {
    return `9999${text}`
  }
  return `${match[3]}${match[2]}${match[1]}${match[4]}${match[5]}`
}

/** Xoay danh sách kết quả thành bảng: mỗi dòng một xét nghiệm, mỗi cột một thời điểm lấy mẫu. */
export function buildLabPivot(labs: readonly ChiTietXetNghiemDong[]): LabPivot {
  const times = [...new Set(labs.map((lab) => formatClinicalText(lab.thoi_diem_text)))].sort(
    (a, b) => timeSortKey(a).localeCompare(timeSortKey(b)),
  )
  const rowByName = new Map<string, LabPivotRow>()
  for (const lab of labs) {
    let row = rowByName.get(lab.ten)
    if (!row) {
      row = {
        name: lab.ten,
        unit: formatClinicalText(lab.don_vi),
        reference: formatClinicalText(lab.khoang_tham_chieu),
        cells: times.map(() => null),
        hasAbnormal: false,
      }
      rowByName.set(lab.ten, row)
    }
    const parsedValue = parseTrendValue(lab.gia_tri_text)
    const direction = parseTrendValue(lab.huong ?? '').direction ?? parsedValue.direction
    const col = times.indexOf(formatClinicalText(lab.thoi_diem_text))
    row.cells[col] = {
      text: formatClinicalText(parsedValue.text),
      abnormal: lab.ngoai_nguong,
      direction,
    }
    if (lab.ngoai_nguong) {
      row.hasAbnormal = true
    }
  }
  return { times, rows: [...rowByName.values()] }
}

/* ---------- Ma trận tương tác thuốc ---------- */

export type InteractionLevel =
  | 'nghiem_trong'
  | 'can_luu_y'
  | 'thieu_du_lieu'
  | 'khong_phat_hien'
  | 'khong_ap_dung'
  | 'chua_kiem'

export interface InteractionDrug {
  name: string
  /** Mã dòng khi có ma trận, tên rút gọn khi dùng hợp đồng cũ. */
  key: string
  group: 'cho_duyet' | 'dang_dung'
}

export interface InteractionPair {
  a: number
  b: number
  level: InteractionLevel
  finding: NhanDinh | null
  findingId: string | null
  reason: string | null
  summary: string | null
}

export interface InteractionMatrixData {
  drugs: InteractionDrug[]
  pairs: InteractionPair[]
  /** Yếu tố tương tác chưa có luật chạy cho ca này. */
  untested: boolean
  foods: TuongTacThucAn[]
  source: string | null
  note: string | null
}

export const INTERACTION_LEVEL_META: Record<
  InteractionLevel,
  { code: string; label: string; hint: string }
> = {
  nghiem_trong: { code: 'N', label: 'Nghiêm trọng', hint: 'Cần xem lại phối hợp' },
  can_luu_y: { code: 'L', label: 'Cần lưu ý', hint: 'Theo dõi khi phối hợp' },
  thieu_du_lieu: { code: 'T', label: 'Thiếu dữ liệu', hint: 'Chưa đủ dữ liệu để kết luận' },
  khong_phat_hien: { code: 'K', label: 'Không phát hiện', hint: 'Luật đã chạy, không ghi nhận' },
  khong_ap_dung: { code: '–', label: 'Không áp dụng', hint: 'Dịch truyền, điện giải hoặc dược liệu' },
  chua_kiem: { code: '?', label: 'Chưa kiểm', hint: 'Chưa có luật cho cặp này' },
}

/** Rút tên hoạt chất: lấy các từ đứng trước từ đầu tiên bắt đầu bằng chữ số. */
export function drugKey(name: string): string {
  const tokens = name.trim().split(/\s+/)
  const kept: string[] = []
  for (const token of tokens) {
    if (/^\d/.test(token)) {
      break
    }
    kept.push(token)
  }
  return (kept.length > 0 ? kept.join(' ') : name).toLowerCase()
}

function isFactor(yeuTo: string, index: number): boolean {
  const trimmed = yeuTo.trim()
  return trimmed.startsWith(`${index}.`) || trimmed.startsWith(`${index} ·`)
}

/** Dựng ma trận từng cặp thuốc từ nhận định thuộc yếu tố 4 (tương tác thuốc). Không suy diễn ngoài dữ liệu. */
export function buildInteractionMatrix(
  choDuyet: BangYLenh,
  dangDung: BangYLenh | null,
  nhanDinh: {
    can_chu_y: readonly NhanDinh[]
    dat: readonly NhanDinh[]
    yeu_to_chua_kiem: readonly string[]
  },
  matrix?: MaTranTuongTac | null,
): InteractionMatrixData {
  if (matrix != null) {
    const indexById = new Map(matrix.thuoc.map((drug, i) => [drug.chi_tiet_y_lenh_id, i]))
    const findings = new Map([...nhanDinh.can_chu_y, ...nhanDinh.dat].map((row) => [row.nhan_dinh_id, row]))
    const pairs: InteractionPair[] = matrix.cap.flatMap((pair) => {
      const a = indexById.get(pair.a)
      const b = indexById.get(pair.b)
      if (a === undefined || b === undefined || a === b) return []
      return [{ a, b, level: pair.muc,
        finding: pair.nhan_dinh_id ? findings.get(pair.nhan_dinh_id) ?? null : null,
        findingId: pair.nhan_dinh_id, reason: pair.ly_do, summary: pair.tom_tat }]
    })
    return {
      drugs: matrix.thuoc.map((drug) => ({ name: drug.ten, key: drug.chi_tiet_y_lenh_id, group: drug.nhom })),
      pairs, untested: false, foods: matrix.thuc_an, source: matrix.nguon, note: matrix.ghi_chu,
    }
  }
  const drugs: InteractionDrug[] = []
  const seen = new Set<string>()
  const addRows = (table: BangYLenh | null, group: InteractionDrug['group']) => {
    for (const row of table?.dong ?? []) {
      const name = (row['Thuốc'] ?? '').trim()
      if (!name || seen.has(name.toLowerCase())) {
        continue
      }
      seen.add(name.toLowerCase())
      drugs.push({ name, key: drugKey(name), group })
    }
  }
  addRows(choDuyet, 'cho_duyet')
  addRows(dangDung, 'dang_dung')

  const attention = nhanDinh.can_chu_y.filter((item) => isFactor(item.yeu_to, 4))
  const passed = nhanDinh.dat.filter((item) => isFactor(item.yeu_to, 4))
  const untested =
    nhanDinh.yeu_to_chua_kiem.some((label) => isFactor(label, 4)) ||
    (attention.length === 0 && passed.length === 0)

  const pairs: InteractionPair[] = []
  for (let a = 0; a < drugs.length; a += 1) {
    for (let b = a + 1; b < drugs.length; b += 1) {
      const finding =
        attention.find((item) => {
          const haystack = `${item.thuoc} ${item.nhan_xet}`.toLowerCase()
          return haystack.includes(drugs[a].key) && haystack.includes(drugs[b].key)
        }) ?? null
      let level: InteractionLevel
      if (finding) {
        level =
          finding.ket_luan_ma === 'khong_du_du_lieu'
            ? 'thieu_du_lieu'
            : finding.muc_do_ma === 'nghiem_trong'
              ? 'nghiem_trong'
              : 'can_luu_y'
      } else {
        level = untested ? 'chua_kiem' : 'khong_phat_hien'
      }
      pairs.push({ a, b, level, finding, findingId: finding?.nhan_dinh_id ?? null, reason: null, summary: null })
    }
  }
  return { drugs, pairs, untested, foods: [], source: null, note: null }
}

/** Tóm tắt một dòng cho tiêu đề ma trận khi đang thu gọn, ví dụ "3 thuốc · 1 cặp nghiêm trọng". */
export function summarizeInteraction(data: InteractionMatrixData): string {
  const drugs = `${data.drugs.length} thuốc`
  if (data.drugs.length < 2) {
    return `${drugs} · không có cặp để đối chiếu`
  }
  if (data.untested) {
    return `${drugs} · chưa kiểm tương tác`
  }
  const count = (level: string) => data.pairs.filter((pair) => pair.level === level).length
  const parts: string[] = []
  const severe = count('nghiem_trong')
  const caution = count('can_luu_y')
  const missing = count('thieu_du_lieu')
  if (severe > 0) parts.push(`${severe} cặp nghiêm trọng`)
  if (caution > 0) parts.push(`${caution} cặp cần lưu ý`)
  if (missing > 0) parts.push(`${missing} cặp thiếu dữ liệu`)
  if (parts.length === 0) {
    const applicable = data.pairs.filter((pair) => pair.level !== 'khong_ap_dung').length
    parts.push(applicable === 0 ? 'không có cặp áp dụng' : 'không ghi nhận cặp cần lưu ý')
  }
  return `${drugs} · ${parts.join(' · ')}`
}
