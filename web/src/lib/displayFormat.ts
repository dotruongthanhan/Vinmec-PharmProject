import type { SemanticTone } from './severity.ts'

export type TrendDirection = 'up' | 'down'

export interface ParsedTrendValue {
  text: string
  direction: TrendDirection | null
}

export interface ParsedLeadingSymbolLabel {
  text: string
  tone: SemanticTone | null
}

const ISO_TIMESTAMP_PATTERN =
  /\b(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?\b/g

const VIETNAM_OFFSET_MS = 7 * 60 * 60 * 1000

/** Tách ký tự mũi tên tăng/giảm khỏi chuỗi giá trị để thay bằng biểu tượng. */
export function parseTrendValue(raw: string): ParsedTrendValue {
  const hasUp = raw.includes('\u25B2')
  const hasDown = raw.includes('\u25BC')
  if (!hasUp && !hasDown) {
    return { text: raw, direction: null }
  }
  const direction: TrendDirection = hasUp ? 'up' : 'down'
  const text = raw.replace(/\s*[\u25B2\u25BC]+\s*/g, ' ').trim()
  return { text, direction }
}

/** Bỏ ký tự cảnh báo hoặc dấu tích ở đầu nhãn API và suy ra tông nghĩa gợi ý. */
export function parseLeadingSymbolLabel(raw: string): ParsedLeadingSymbolLabel {
  const match = /^\s*([\u26A0\u2713])\uFE0F?\s*([\s\S]*)$/.exec(raw)
  if (!match) {
    return { text: raw, tone: null }
  }
  const tone: SemanticTone = match[1] === '\u26A0' ? 'warning' : 'success'
  return { text: match[2], tone }
}

/** Định dạng chuỗi thời điểm ISO 8601 (kèm múi giờ) sang HH:MM · DD/MM/YYYY theo giờ Việt Nam (+07:00). */
export function formatIsoTimestamp(raw: string): string {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$/.exec(
      raw.trim(),
    )
  if (!match) {
    return raw
  }

  const [, yearStr, monthStr, dayStr, hourStr, minStr, secStr, tz] = match
  if (!tz) {
    return `${hourStr}:${minStr} · ${dayStr}/${monthStr}/${yearStr}`
  }

  const normalizedTz =
    tz !== 'Z' && /^[+-]\d{4}$/.test(tz) ? `${tz.slice(0, 3)}:${tz.slice(3)}` : tz
  const isoNorm = `${yearStr}-${monthStr}-${dayStr}T${hourStr}:${minStr}:${secStr ?? '00'}${normalizedTz}`
  const ms = Date.parse(isoNorm)
  if (!Number.isFinite(ms)) {
    return raw
  }

  const vnDate = new Date(ms + VIETNAM_OFFSET_MS)
  const hh = String(vnDate.getUTCHours()).padStart(2, '0')
  const mm = String(vnDate.getUTCMinutes()).padStart(2, '0')
  const dd = String(vnDate.getUTCDate()).padStart(2, '0')
  const mo = String(vnDate.getUTCMonth() + 1).padStart(2, '0')
  const yyyy = String(vnDate.getUTCFullYear())
  return `${hh}:${mm} · ${dd}/${mo}/${yyyy}`
}

/** Chuyển mọi thời điểm dạng ISO xuất hiện trong văn bản sang HH:MM · DD/MM/YYYY. */
export function formatIsoTimestampsInText(text: string): string {
  return text.replace(ISO_TIMESTAMP_PATTERN, (full) => formatIsoTimestamp(full))
}

/** Chuẩn hoá đơn vị xét nghiệm thô (ví dụ umol/L → µmol/L). */
export function formatClinicalUnits(text: string): string {
  return text.replace(/\bumol\/[lL]\b/g, 'µmol/L')
}

/** Chuẩn hoá mã loại cân nặng nội bộ sang tiếng Việt hiển thị. */
export function formatWeightTypes(text: string): string {
  return text
    .replace(/\bthuc_te\b/g, 'thực tế')
    .replace(/\bly_tuong\b/g, 'lý tưởng')
    .replace(/\bhieu_chinh\b/g, 'hiệu chỉnh')
}

/** Đổi dấu chấm thập phân thành dấu phẩy cho số đo lâm sàng, giữ nguyên mã ICD-10 và chuỗi nhiều chấm. */
export function formatDecimalCommas(text: string): string {
  return text.replace(/(?<![A-Za-z0-9_.])(\d+)\.(\d+)(?!\.\d)/g, '$1,$2')
}

/** Dọn toàn bộ chuỗi thô từ API ở tầng hiển thị: thời điểm ISO, đơn vị, loại cân nặng và dấu phẩy thập phân. */
export function formatClinicalText(text: string): string {
  if (!text) {
    return text
  }
  const step1 = formatIsoTimestampsInText(text)
  const step2 = formatClinicalUnits(step1)
  const step3 = formatWeightTypes(step2)
  return formatDecimalCommas(step3)
}

/** Định dạng thời điểm dạng DD/MM/YYYY HH:MM hoặc ISO thành HH:MM · DD/MM/YYYY. */
export function formatReadableDateTime(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) {
    return raw
  }
  if (trimmed.includes('T')) {
    return formatIsoTimestamp(trimmed)
  }
  const dmyMatch = /^(\d{2}\/\d{2}\/\d{4})\s+(\d{2}:\d{2})$/.exec(trimmed)
  if (dmyMatch) {
    return `${dmyMatch[2]} · ${dmyMatch[1]}`
  }
  return trimmed
}

/** Trích mã y lệnh từ dòng thông tin y lệnh nếu có, nếu không trả về mã ca. */
export function extractOrderCode(thongTinText: string, fallbackCaId: string): string {
  const match = /Mã y lệnh:\s*([^\s·]+)/i.exec(thongTinText)
  return match?.[1] ? match[1].trim() : fallbackCaId
}

/** Trích thời điểm kê từ dòng thông tin y lệnh nếu có. */
export function extractOrderTimeText(thongTinText: string): string | null {
  const match = /Thời điểm kê:\s*([^·]+)$/i.exec(thongTinText)
  return match?.[1] ? match[1].trim() : null
}
