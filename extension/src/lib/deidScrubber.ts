/**
 * Lớp che định danh tại trình duyệt (bản chuyển đổi tương đương app/deid/scrubber.py + session.py).
 * Luôn chạy thất bại đóng (fail-closed): lỗi không mong muốn sẽ dừng trước khi gửi mạng.
 */

import {
  buildGroupLookup,
  foldVietnamese,
  isQuasiDobLabel,
  matchesLocalPiiFloor,
} from './schemaCache'
import type {
  ClassifiedField,
  DeidAuditSummary,
  DeidReplacement,
  EmrSectionPayload,
  RawTabExtraction,
} from './types'

export class LocalDeidError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'LocalDeidError'
  }
}

export interface ScrubResult {
  van_ban: string
  thay_the: DeidReplacement[]
  anh_xa: Record<string, string>
}

interface PatternSpan {
  start: number
  end: number
  kind: 'EMAIL' | 'BHYT' | 'CCCD' | 'SDT' | 'HN' | 'NGAY' | 'TEN'
  priority: number
}

const UPPER_VI =
  'A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ'
const LOWER_VI =
  'a-zàáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ'
const LETTER_VI = `${UPPER_VI}${LOWER_VI}`
const WORD_VI = `[${UPPER_VI}][${LOWER_VI}]*`

const EMAIL_RE =
  /(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+-])/g
const BHYT_RE = /(?<![A-Za-z0-9])[A-Za-z]{2}\d{13}(?![A-Za-z0-9])/g
const CCCD_RE = /(?<![A-Za-z0-9.,])0\d{11}(?![A-Za-z0-9.,])/g
const SDT_RE = /(?<![A-Za-z0-9+])(?:\+?84|0)(?:3|5|7|8|9)(?:[\s.-]?\d){8}(?![A-Za-z0-9])/g
const HN_RE = /(?<![A-Za-z0-9.,])\d{9}(?![A-Za-z0-9.,])/g

const FULL_DATE_RE =
  /(?<![A-Za-z0-9/.-])(0?[1-9]|[12]\d|3[01])([/.-])(0?[1-9]|1[0-2])\2((?:19|20)\d{2})(?![A-Za-z0-9/-]|\.\d)/g
const ISO_DATE_RE =
  /(?<![A-Za-z0-9/.-])((?:19|20)\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])(?![A-Za-z0-9/-]|\.\d)/g
const NON_CLINICAL_DATE_PREFIX_RE =
  /(?:ngày\s+sinh|năm\s+sinh|sinh|hạn|hết\s+hạn|giá\s+trị\s+đến)\s*:?\s*$/iu
const SHORT_DATE_RE =
  /(?<![A-Za-z0-9/.,])(0?[1-9]|[12]\d|3[01])\/(0?[1-9]|1[0-2])(?![A-Za-z0-9/.,])/g

const TITLE_NAME_RE = new RegExp(
  `(?<![${LETTER_VI}0-9])(bệnh\\s+nhân|bác\\s+sĩ|điều\\s+dưỡng|dược\\s+sĩ|BS|BN|ĐD|DS|chị|anh|ông|bà|cô|chú)(\\.?\\s+|:\\s*)(${WORD_VI}(?:\\s+${WORD_VI}){0,4})`,
  'gu',
)

const CLINICAL_UNIT_FOLLOW_RE =
  /^\s*(?:mmhg|\/l|\/ul|\/ml|iu\/ml|ui\/ml|mmol\/l|umol\/l|µmol\/l|mg\/dl|mg\/l|g\/l|g\/dl|u\/l|copies\/ml|ng\/ml|pg\/ml|meq\/l|lần\/phút|nhịp\/phút|ml\/phút|ml\/min|%|mg|mcg|g|kg|cm|ml)(?![A-Za-z0-9])/iu

const FRACTION_PREFIX_RE =
  /(?:liều|uống|dùng|tiêm|truyền|tỉ\s*lệ|tỷ\s*lệ|tỉ\s*số|tỷ\s*số)\s*:?\s*$/iu
const FRACTION_SUFFIX_RE = /^\s*(?:viên|ống|gói|giọt|thìa|muỗng|lọ|bơm|ml|mg|g)\b/iu
const GENDER_ONLY = new Set(['nam', 'nữ', 'nu'])

function isValidCalendarDate(day: number, month: number): boolean {
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    return false
  }
  const maxByMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return day <= maxByMonth[month - 1]
}

function collectPatternSpans(nfcText: string): PatternSpan[] {
  const spans: PatternSpan[] = []

  const addMatches = (
    re: RegExp,
    kind: PatternSpan['kind'],
    priority: number,
    filter?: (match: RegExpExecArray) => { start: number; end: number } | null,
  ) => {
    re.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = re.exec(nfcText)) !== null) {
      if (filter) {
        const range = filter(match)
        if (range) {
          spans.push({ ...range, kind, priority })
        }
      } else {
        spans.push({
          start: match.index,
          end: match.index + match[0].length,
          kind,
          priority,
        })
      }
    }
  }

  addMatches(EMAIL_RE, 'EMAIL', 1)
  addMatches(BHYT_RE, 'BHYT', 2)
  addMatches(CCCD_RE, 'CCCD', 3, (m) => {
    const end = m.index + m[0].length
    if (CLINICAL_UNIT_FOLLOW_RE.test(nfcText.slice(end))) {
      return null
    }
    return { start: m.index, end }
  })
  addMatches(SDT_RE, 'SDT', 4)
  addMatches(HN_RE, 'HN', 5, (m) => {
    const end = m.index + m[0].length
    if (CLINICAL_UNIT_FOLLOW_RE.test(nfcText.slice(end))) {
      return null
    }
    return { start: m.index, end }
  })
  addMatches(FULL_DATE_RE, 'NGAY', 6, (m) => {
    const day = Number.parseInt(m[1], 10)
    const month = Number.parseInt(m[3], 10)
    if (!isValidCalendarDate(day, month)) {
      return null
    }
    return { start: m.index, end: m.index + m[0].length }
  })
  addMatches(SHORT_DATE_RE, 'NGAY', 7, (m) => {
    const day = Number.parseInt(m[1], 10)
    const month = Number.parseInt(m[2], 10)
    if (!isValidCalendarDate(day, month)) {
      return null
    }
    const start = m.index
    const end = start + m[0].length
    const before = nfcText.slice(Math.max(0, start - 20), start)
    const after = nfcText.slice(end, end + 20)
    if (FRACTION_PREFIX_RE.test(before) || FRACTION_SUFFIX_RE.test(after)) {
      return null
    }
    return { start, end }
  })
  addMatches(TITLE_NAME_RE, 'TEN', 8, (m) => {
    const title = m[1]
    const sep = m[2]
    const namePart = m[3]
    if (/^(?:BN|bệnh\s+nhân)$/iu.test(title) && GENDER_ONLY.has(namePart.trim().toLowerCase())) {
      return null
    }
    const nameStart = m.index + title.length + sep.length
    const nameEnd = nameStart + namePart.length
    return { start: nameStart, end: nameEnd }
  })

  spans.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start
    if (a.priority !== b.priority) return a.priority - b.priority
    return b.end - b.start - (a.end - a.start)
  })

  const accepted: PatternSpan[] = []
  for (const span of spans) {
    const overlap = accepted.some((prev) => !(span.end <= prev.start || span.start >= prev.end))
    if (!overlap) {
      accepted.push(span)
    }
  }
  return accepted
}

export function scrubText(rawText: string): ScrubResult {
  const text = rawText.normalize('NFC')
  const spans = collectPatternSpans(text)
  if (spans.length === 0) {
    return { van_ban: rawText, thay_the: [], anh_xa: {} }
  }

  const counters: Record<string, number> = {}
  const tokenByKey = new Map<string, string>()
  const anhXa: Record<string, string> = {}
  const thayThe: DeidReplacement[] = []

  let out = ''
  let cursor = 0
  for (const span of spans) {
    const original = text.slice(span.start, span.end)
    const key = `${span.kind}:${original}`
    let token = tokenByKey.get(key)
    if (!token) {
      const nextIdx = (counters[span.kind] ?? 0) + 1
      counters[span.kind] = nextIdx
      token = `[${span.kind}_${nextIdx}]`
      tokenByKey.set(key, token)
      anhXa[token] = original
    }
    thayThe.push({ loai: span.kind, ma_tam: token })
    out += text.slice(cursor, span.start) + token
    cursor = span.end
  }
  out += text.slice(cursor)
  return { van_ban: out, thay_the: thayThe, anh_xa: anhXa }
}

/** Tính số tuổi nguyên từ ngày sinh (DD/MM/YYYY hoặc YYYY-MM-DD) rồi bỏ ngày sinh gốc. */
export function dobToAgeYears(rawDob: string, now: Date = new Date()): number | null {
  const cleaned = rawDob.trim()
  let year = 0
  let month = 1
  let day = 1

  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(cleaned)
  const dmy = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(cleaned)
  const yearOnly = /^(\d{4})$/.exec(cleaned)
  if (iso) {
    year = Number.parseInt(iso[1], 10)
    month = Number.parseInt(iso[2], 10)
    day = Number.parseInt(iso[3], 10)
  } else if (dmy) {
    day = Number.parseInt(dmy[1], 10)
    month = Number.parseInt(dmy[2], 10)
    year = Number.parseInt(dmy[3], 10)
  } else if (yearOnly) {
    year = Number.parseInt(yearOnly[1], 10)
  } else {
    return null
  }

  if (year < 1900 || year > now.getFullYear()) {
    return null
  }
  let age = now.getFullYear() - year
  const currMonth = now.getMonth() + 1
  const currDay = now.getDate()
  if (currMonth < month || (currMonth === month && currDay < day)) {
    age -= 1
  }
  return age >= 0 && age <= 120 ? age : null
}

/** Lớp 1: Thu thập toàn bộ giá trị PII đã cắt khỏi `<dt>/<dd>` để quét sạch trong văn bản tự do. */
export class LocalDeidSession {
  private readonly knownTerms: Array<{ folded: string; token: string }> = []
  private knownCount = 0

  addKnownPii(rawValue: string, kind: 'TEN' | 'ID' | 'DIACHI' = 'ID'): void {
    const cleaned = rawValue.trim()
    if (cleaned.length < 3) {
      return
    }
    const folded = foldVietnamese(cleaned)
    if (folded.length < 3) {
      return
    }
    if (this.knownTerms.some((item) => item.folded === folded)) {
      return
    }
    this.knownCount += 1
    this.knownTerms.push({ folded, token: `[${kind}_${this.knownCount}]` })
    this.knownTerms.sort((a, b) => b.folded.length - a.folded.length)
  }

  scrubKnownValues(text: string): { text: string; replacements: number } {
    if (this.knownTerms.length === 0 || !text) {
      return { text, replacements: 0 }
    }
    let current = text
    let replacements = 0

    for (const entry of this.knownTerms) {
      const foldedCurrent = foldVietnamese(current)
      if (!foldedCurrent.includes(entry.folded)) {
        continue
      }

      const chars = Array.from(current.normalize('NFC'))
      const charFolded: string[] = []
      const mapFoldedIdxToOrig: number[] = []
      let lastWasSpace = true
      for (let i = 0; i < chars.length; i += 1) {
        const piece = foldVietnamese(chars[i])
        if (!piece) {
          if (!lastWasSpace && /[\s_:./-]/.test(chars[i])) {
            charFolded.push(' ')
            mapFoldedIdxToOrig.push(i)
            lastWasSpace = true
          }
          continue
        }
        for (const ch of piece) {
          charFolded.push(ch)
          mapFoldedIdxToOrig.push(i)
        }
        lastWasSpace = false
      }

      const normStr = charFolded.join('')
      const matchRanges: Array<{ start: number; end: number }> = []
      let searchPos = 0
      while (searchPos < normStr.length) {
        const hit = normStr.indexOf(entry.folded, searchPos)
        if (hit === -1) break
        const origStart = mapFoldedIdxToOrig[hit]
        const endFoldIdx = hit + entry.folded.length - 1
        const origEnd = mapFoldedIdxToOrig[endFoldIdx] + 1
        matchRanges.push({ start: origStart, end: origEnd })
        searchPos = hit + entry.folded.length
      }
      if (matchRanges.length > 0) {
        let rebuilt = ''
        let pos = 0
        for (const range of matchRanges) {
          rebuilt += chars.slice(pos, range.start).join('') + entry.token
          pos = range.end
          replacements += 1
        }
        rebuilt += chars.slice(pos).join('')
        current = rebuilt
      }
    }
    return { text: current, replacements }
  }

  scrubAll(text: string): { text: string; regexCounts: Record<string, number>; knownHits: number } {
    try {
      const layer1 = this.scrubKnownValues(text)
      const layer2 = scrubText(layer1.text)
      const regexCounts: Record<string, number> = {}
      for (const item of layer2.thay_the) {
        regexCounts[item.loai] = (regexCounts[item.loai] ?? 0) + 1
      }
      return {
        text: layer2.van_ban,
        regexCounts,
        knownHits: layer1.replacements,
      }
    } catch (err) {
      throw new LocalDeidError(
        `Lỗi che định danh cục bộ (đã chặn gửi mạng): ${err instanceof Error ? err.message : 'unknown'}`,
      )
    }
  }
}

interface ParsedDateSpan {
  start: number
  end: number
  utcDay: number
  displayDate: string
}

const MS_PER_DAY = 86_400_000

function toUtcDay(year: number, month: number, day: number): number | null {
  if (!isValidCalendarDate(day, month)) return null
  const dt = new Date(Date.UTC(year, month - 1, day))
  if (
    dt.getUTCFullYear() !== year ||
    dt.getUTCMonth() !== month - 1 ||
    dt.getUTCDate() !== day
  ) {
    return null
  }
  return Math.floor(dt.getTime() / MS_PER_DAY)
}

function collectClinicalDateSpans(text: string): ParsedDateSpan[] {
  const spans: ParsedDateSpan[] = []

  const scan = (re: RegExp, parse: (m: RegExpExecArray) => { y: number; mo: number; d: number }) => {
    re.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = re.exec(text)) !== null) {
      const before = text.slice(Math.max(0, m.index - 28), m.index)
      if (NON_CLINICAL_DATE_PREFIX_RE.test(before)) {
        continue
      }
      const { y, mo, d } = parse(m)
      const utcDay = toUtcDay(y, mo, d)
      if (utcDay === null) continue
      const pad2 = (n: number) => String(n).padStart(2, '0')
      spans.push({
        start: m.index,
        end: m.index + m[0].length,
        utcDay,
        displayDate: `${pad2(d)}/${pad2(mo)}/${y}`,
      })
    }
  }

  scan(FULL_DATE_RE, (m) => ({
    d: Number.parseInt(m[1], 10),
    mo: Number.parseInt(m[3], 10),
    y: Number.parseInt(m[4], 10),
  }))
  scan(ISO_DATE_RE, (m) => ({
    y: Number.parseInt(m[1], 10),
    mo: Number.parseInt(m[2], 10),
    d: Number.parseInt(m[3], 10),
  }))

  spans.sort((a, b) => a.start - b.start)
  const accepted: ParsedDateSpan[] = []
  for (const sp of spans) {
    if (!accepted.some((prev) => !(sp.end <= prev.start || sp.start >= prev.end))) {
      accepted.push(sp)
    }
  }
  return accepted
}

/**
 * Quy đổi toàn bộ ngày lâm sàng đầy đủ trên nhiều văn bản sang mốc tương đối (`Ngày +0`, `Ngày +30`...)
 * dựa trên ngày sớm nhất làm mốc `Ngày +0`, đồng thời trả bảng ánh xạ giữ cục bộ tại trình duyệt.
 */
export function shiftClinicalDates(texts: string[]): {
  shifted: string[]
  restoreMap: Record<string, string>
} {
  const perTextSpans = texts.map((t) => collectClinicalDateSpans(t))
  let minUtcDay = Number.POSITIVE_INFINITY
  for (const spans of perTextSpans) {
    for (const sp of spans) {
      if (sp.utcDay < minUtcDay) {
        minUtcDay = sp.utcDay
      }
    }
  }

  if (!Number.isFinite(minUtcDay)) {
    return { shifted: texts, restoreMap: {} }
  }

  const restoreMap: Record<string, string> = {}
  const shifted = texts.map((text, idx) => {
    const spans = perTextSpans[idx]
    if (spans.length === 0) return text
    let out = ''
    let cursor = 0
    for (const sp of spans) {
      const delta = sp.utcDay - minUtcDay
      const label = `Ngày +${delta}`
      restoreMap[label] = sp.displayDate
      out += text.slice(cursor, sp.start) + label
      cursor = sp.end
    }
    out += text.slice(cursor)
    return out
  })

  return { shifted, restoreMap }
}

/** Gắn chú thích ngày gốc cục bộ ngay trên giao diện trình duyệt (không bao giờ gửi lên server). */
export function restoreLocalLabels(text: string, restoreMap: Record<string, string>): string {
  const entries = Object.entries(restoreMap)
  if (entries.length === 0 || !text) return text
  return text.replace(/Ngày \+\d+/g, (token) => {
    const orig = restoreMap[token]
    return orig ? `${token} (${orig})` : token
  })
}

export function sanitizeTabsForUpload(
  tabs: RawTabExtraction[],
  classifiedFields: ClassifiedField[],
  now: Date = new Date(),
): {
  sections: EmrSectionPayload[]
  audit: DeidAuditSummary
  restoreMap: Record<string, string>
} {
  const groupLookup = buildGroupLookup(classifiedFields)
  const session = new LocalDeidSession()
  const droppedFields = new Set<string>()
  const quasiTransforms: string[] = []
  const regexTotals: Record<string, number> = {}
  let knownValueRedactions = 0

  interface DraftBlock {
    tieu_de: string
    loai_muc: EmrSectionPayload['loai_muc']
    tab_id: number
    tab_title: string
    rawText: string
  }
  const drafts: DraftBlock[] = []

  for (const tab of tabs) {
    const keptLines: string[] = []
    for (const pair of tab.fieldPairs) {
      const foldedLabel = foldVietnamese(pair.label)
      const group = groupLookup.get(foldedLabel)
      const isPii =
        matchesLocalPiiFloor(pair.label, pair.sectionTitle) ||
        group === 'pii_xoa' ||
        group === 'nghi_ngo_pii' ||
        !group

      if (isQuasiDobLabel(pair.label)) {
        droppedFields.add(pair.label)
        session.addKnownPii(pair.value, 'ID')
        const age = dobToAgeYears(pair.value, now)
        if (age !== null) {
          keptLines.push(`Tuổi (quy đổi từ ngày sinh): ${age} tuổi`)
          quasiTransforms.push(`${pair.label} -> ${age} tuổi`)
        }
        continue
      }

      if (isPii) {
        droppedFields.add(pair.label)
        const piiKind =
          foldedLabel.includes('ten') || foldedLabel.includes('bac si')
            ? 'TEN'
            : foldedLabel.includes('dia chi')
              ? 'DIACHI'
              : 'ID'
        session.addKnownPii(pair.value, piiKind)
        continue
      }

      keptLines.push(`${pair.label}: ${pair.value}`)
    }

    if (keptLines.length > 0) {
      drafts.push({
        tieu_de: `Thông tin cấu trúc (${tab.tabTitle || 'EMR'})`,
        loai_muc: 'demographics_dx',
        tab_id: tab.tabId,
        tab_title: tab.tabTitle.slice(0, 160),
        rawText: keptLines.join('\n'),
      })
    }

    for (const sec of tab.sections) {
      if (!sec.text.trim()) continue
      drafts.push({
        tieu_de: sec.title.slice(0, 150),
        loai_muc: sec.bucket,
        tab_id: tab.tabId,
        tab_title: tab.tabTitle.slice(0, 160),
        rawText: sec.text,
      })
    }
  }

  // Bước 2b: Quy đổi toàn bộ mốc ngày lâm sàng đầy đủ trên tất cả tab về cùng gốc Ngày +0.
  const { shifted, restoreMap } = shiftClinicalDates(drafts.map((d) => d.rawText))

  const sections: EmrSectionPayload[] = []
  let totalCharsOut = 0

  for (let i = 0; i < drafts.length; i += 1) {
    const draft = drafts[i]
    const cleaned = session.scrubAll(shifted[i])
    knownValueRedactions += cleaned.knownHits
    for (const [k, v] of Object.entries(cleaned.regexCounts)) {
      regexTotals[k] = (regexTotals[k] ?? 0) + v
    }
    const finalBody = cleaned.text.trim()
    if (!finalBody) continue
    sections.push({
      tieu_de: draft.tieu_de,
      loai_muc: draft.loai_muc,
      tab_id: draft.tab_id,
      tab_title: draft.tab_title,
      noi_dung: finalBody.slice(0, 38_000),
    })
    totalCharsOut += finalBody.length
  }

  return {
    sections,
    audit: {
      droppedFields: Array.from(droppedFields),
      quasiTransforms,
      regexRedactions: regexTotals,
      knownValueRedactions,
      dateAnchorCount: Object.keys(restoreMap).length,
      totalCharsOut,
    },
    restoreMap,
  }
}
