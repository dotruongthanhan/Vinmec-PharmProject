/**
 * Bộ trích xuất DOM đa năng cho ứng dụng web hiện tại (PatientSidebarCard, AdministrativeSections,
 * DetailSections, MedicalRecordSections) và các EMR bệnh viện tương lai.
 * - Dùng `textContent` để đọc được cả `<details>` đang đóng.
 * - Đọc thẻ tóm tắt bệnh nhân trong `<aside aria-label="Thanh bên điều hướng">` (bỏ qua `<nav>` và khối Chỉ số tính sẵn).
 * - Tự động loại trừ `<aside aria-label="Khung trợ lý AI">`, `[id^="finding-"]`, và thẻ `Thẩm định` có sẵn.
 */

import { foldVietnamese } from './schemaCache'
import type {
  ExtractedFieldPair,
  ExtractedSection,
  RawTabExtraction,
  SchemaFieldDescriptor,
} from './types'

export interface DomElementLike {
  tagName: string
  id?: string
  textContent: string | null
  getAttribute(name: string): string | null
  querySelectorAll(selector: string): ArrayLike<DomElementLike>
  closest?(selector: string): DomElementLike | null
  children?: ArrayLike<DomElementLike>
  nextElementSibling?: DomElementLike | null
}

export interface DomDocumentLike {
  title: string
  location?: { href: string; origin: string }
  body?: DomElementLike | null
  querySelectorAll(selector: string): ArrayLike<DomElementLike>
}

const EXCLUDED_SELECTOR =
  'nav, header, footer, script, style, noscript, [id^="finding-"], [data-testid="ai-review-drawer"], [data-cdss-ignore="true"], [aria-label="Bốn chỉ số lâm sàng"]'

const SIDEBAR_LABELED_BLOCKS = new Set(['bhyt', 'di ung', 'chan doan'])

// Bỏ qua tiêu đề cột động dạng ngày giờ (vd. "26/09/2026 08:00" ở bảng xét nghiệm) hoặc chuỗi mang số định danh.
const DYNAMIC_HEADER_VALUE_RE =
  /(?:\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b|@|\b0\d{11}\b|\b[A-Za-z]{2}\d{13}\b|\b\d{9}\b)/

function cleanText(raw: string | null | undefined): string {
  return (raw ?? '').replace(/\s+/g, ' ').trim()
}

function isExcludedAside(asideEl: DomElementLike): boolean {
  const id = asideEl.id ?? ''
  if (id.startsWith('finding-')) {
    return true
  }
  if (asideEl.getAttribute('data-testid') === 'ai-review-drawer') {
    return true
  }
  const aria = foldVietnamese(asideEl.getAttribute('aria-label') ?? '')
  if (!aria) {
    // Mặc định an toàn: chỉ đọc <aside> có nhãn rõ ràng (vd. Thanh bên điều hướng),
    // bỏ qua các <aside> vô danh thường dùng cho drawer phụ/quảng cáo/kết quả AI.
    return true
  }
  return aria.includes('tham dinh') || aria.includes('tro ly ai') || aria.includes('nhan dinh')
}

function isInsideExcluded(el: DomElementLike): boolean {
  if (typeof el.closest === 'function') {
    if (el.closest(EXCLUDED_SELECTOR) !== null) {
      return true
    }
    const parentAside = el.closest('aside')
    if (parentAside !== null && isExcludedAside(parentAside)) {
      return true
    }
  }
  const id = el.id ?? ''
  if (id.startsWith('finding-')) {
    return true
  }
  const aria = foldVietnamese(el.getAttribute('aria-label') ?? '')
  if (
    aria.includes('tham dinh') ||
    aria.includes('tro ly ai') ||
    aria.includes('nhan dinh') ||
    aria.includes('chi so lam sang')
  ) {
    return true
  }
  return false
}

function inferBucket(title: string): ExtractedSection['bucket'] {
  const folded = foldVietnamese(title)
  if (
    folded.includes('xet nghiem') ||
    folded.includes('sinh hieu') ||
    folded.includes('can lam sang') ||
    folded.includes('vi sinh') ||
    folded.includes('khang sinh do')
  ) {
    return 'labs_vitals'
  }
  if (
    folded.includes('hanh chinh') ||
    folded.includes('chan doan') ||
    folded.includes('di ung') ||
    folded.includes('co dia') ||
    folded.includes('quan ly nguoi benh') ||
    folded.includes('thanh ben')
  ) {
    return 'demographics_dx'
  }
  if (
    folded.includes('y lenh') ||
    folded.includes('thuoc') ||
    folded.includes('dien bien') ||
    folded.includes('phieu dieu tri') ||
    folded.includes('hoi chan')
  ) {
    return 'meds_notes'
  }
  return 'other'
}

export function computeSchemaHash(origin: string, labels: string[]): string {
  const canonical = `${origin}|${[...new Set(labels.map((s) => foldVietnamese(s)))].sort().join('|')}`
  let h1 = 0xdeadbeef ^ canonical.length
  let h2 = 0x41c6ce57 ^ canonical.length
  for (let i = 0; i < canonical.length; i += 1) {
    const ch = canonical.charCodeAt(i)
    h1 = Math.imul(h1 ^ ch, 2654435761)
    h2 = Math.imul(h2 ^ ch, 1597334677)
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)
  const hex =
    (h2 >>> 0).toString(16).padStart(8, '0') + (h1 >>> 0).toString(16).padStart(8, '0')
  return `sch_${hex}`
}

function findNearestSectionTitle(el: DomElementLike): string {
  if (typeof el.closest === 'function') {
    const details = el.closest('details')
    if (details) {
      const summaries = details.querySelectorAll('summary')
      if (summaries.length > 0) {
        const label = cleanText(summaries[0].textContent)
        if (label) return label
      }
    }
    const section = el.closest('section')
    if (section) {
      const aria = cleanText(section.getAttribute('aria-label'))
      if (aria) return aria
      const headings = section.querySelectorAll('h1, h2, h3, h4')
      if (headings.length > 0) {
        const headingText = cleanText(headings[0].textContent)
        if (headingText) return headingText
      }
    }
    const aside = el.closest('aside')
    if (aside && !isExcludedAside(aside)) {
      return 'Thông tin người bệnh (Thanh bên)'
    }
  }
  return 'Thông tin chung'
}

export function extractFromDocument(
  doc: DomDocumentLike,
  tabMeta: { tabId: number; tabTitle?: string; url?: string; origin?: string },
): RawTabExtraction {
  const fieldPairs: ExtractedFieldPair[] = []
  const seenPairKeys = new Set<string>()
  const sections: ExtractedSection[] = []
  const uniqueFieldMap = new Map<string, SchemaFieldDescriptor>()

  const registerField = (
    label: string,
    domKind: ExtractedFieldPair['domKind'],
    sectionTitle: string,
  ) => {
    const cleaned = label.replace(/[:：]\s*$/, '').trim()
    if (!cleaned || cleaned.length > 80 || DYNAMIC_HEADER_VALUE_RE.test(cleaned)) return
    const key = foldVietnamese(cleaned)
    if (!uniqueFieldMap.has(key)) {
      uniqueFieldMap.set(key, {
        ten_nhan: cleaned,
        kieu_dom: domKind,
        ngu_canh_muc: sectionTitle.slice(0, 120),
      })
    }
  }

  const pushPair = (
    label: string,
    value: string,
    domKind: ExtractedFieldPair['domKind'],
    sectionTitle: string,
  ) => {
    const cleanLabel = label.replace(/[:：]\s*$/, '').trim()
    const cleanValue = value.trim()
    if (!cleanLabel || !cleanValue || cleanValue === '—' || cleanValue === '-') return
    registerField(cleanLabel, domKind, sectionTitle)
    const dedupKey = `${foldVietnamese(cleanLabel)}=${foldVietnamese(cleanValue)}`
    if (seenPairKeys.has(dedupKey)) return
    seenPairKeys.add(dedupKey)
    fieldPairs.push({ label: cleanLabel, value: cleanValue, domKind, sectionTitle })
  }

  // 1. Cặp <dl><dt>/<dd> kể cả trong <details> đóng và thẻ tóm tắt bệnh nhân ở thanh bên trái.
  for (const dt of Array.from(doc.querySelectorAll('dt'))) {
    if (isInsideExcluded(dt)) continue
    const dd = dt.nextElementSibling
    if (!dd || dd.tagName.toUpperCase() !== 'DD') continue
    const sectionTitle = findNearestSectionTitle(dt)
    pushPair(cleanText(dt.textContent), cleanText(dd.textContent), 'dt_dd', sectionTitle)
  }

  // 1b. Các khối không dùng <dl> trong thẻ bệnh nhân cột bên trái (Họ tên, Giới tính/Tuổi, BHYT, Dị ứng, Chẩn đoán).
  for (const aside of Array.from(doc.querySelectorAll('aside'))) {
    if (isExcludedAside(aside)) continue
    const sidebarTitle = 'Thông tin người bệnh (Thanh bên)'
    for (const h2 of Array.from(aside.querySelectorAll('h2'))) {
      if (isInsideExcluded(h2)) continue
      const nameText = cleanText(h2.textContent)
      if (nameText) {
        pushPair('Họ tên', nameText, 'colon_pair', sidebarTitle)
      }
      const next = h2.nextElementSibling
      if (next && next.tagName.toUpperCase() === 'P' && !isInsideExcluded(next)) {
        const subText = cleanText(next.textContent)
        if (subText) {
          pushPair('Giới tính / Tuổi', subText, 'colon_pair', sidebarTitle)
        }
      }
    }
    for (const span of Array.from(aside.querySelectorAll('span'))) {
      if (isInsideExcluded(span)) continue
      const rawLabel = cleanText(span.textContent).replace(/[:：]\s*$/, '')
      if (!SIDEBAR_LABELED_BLOCKS.has(foldVietnamese(rawLabel))) continue
      const valueEl = span.nextElementSibling
      if (!valueEl || isInsideExcluded(valueEl)) continue
      pushPair(rawLabel, cleanText(valueEl.textContent), 'colon_pair', sidebarTitle)
    }
  }

  // 2. Bảng <table>.
  const tables = Array.from(doc.querySelectorAll('table'))
  for (let tIdx = 0; tIdx < tables.length; tIdx += 1) {
    const table = tables[tIdx]
    if (isInsideExcluded(table)) continue
    const sectionTitle = findNearestSectionTitle(table)
    if (foldVietnamese(sectionTitle).includes('tham dinh')) continue

    const headers = Array.from(table.querySelectorAll('thead th, tr th')).map((th) =>
      cleanText(th.textContent),
    )
    for (const header of headers) {
      if (header) {
        registerField(header, 'table_th', sectionTitle)
      }
    }

    const bodyRows = Array.from(table.querySelectorAll('tbody tr, tr'))
    const rowLines: string[] = headers.length > 0 ? [headers.join(' | ')] : []
    for (const row of bodyRows) {
      const cells = Array.from(row.querySelectorAll('td')).map((td) => cleanText(td.textContent))
      if (cells.every((c) => !c)) continue
      rowLines.push(cells.join(' | '))
    }
    if (rowLines.length > 1 || (headers.length === 0 && rowLines.length > 0)) {
      sections.push({
        title: `${sectionTitle} (Bảng ${tIdx + 1})`,
        bucket: inferBucket(sectionTitle),
        text: rowLines.join('\n'),
      })
    }
  }

  // 3. Khối <section aria-label> và <details> chứa văn bản tự do.
  for (const el of Array.from(doc.querySelectorAll('section[aria-label], details'))) {
    if (isInsideExcluded(el)) continue
    const aria = cleanText(el.getAttribute('aria-label'))
    const summaryEl = el.querySelectorAll('summary')[0]
    const headingEl = el.querySelectorAll('h2, h3, h4')[0]
    const title = aria || cleanText(summaryEl?.textContent) || cleanText(headingEl?.textContent)
    if (!title || foldVietnamese(title).includes('tham dinh')) continue

    const paragraphs = Array.from(el.querySelectorAll('p, li'))
      .filter((node) => !isInsideExcluded(node))
      .map((node) => cleanText(node.textContent))
      .filter((line) => line.length >= 4)

    if (paragraphs.length > 0) {
      sections.push({
        title,
        bucket: inferBucket(title),
        text: paragraphs.join('\n'),
      })
    }
  }

  const origin = tabMeta.origin ?? doc.location?.origin ?? 'unknown'
  const uniqueFields = Array.from(uniqueFieldMap.values())
  const schemaHash = computeSchemaHash(
    origin,
    uniqueFields.map((f) => f.ten_nhan),
  )

  return {
    tabId: tabMeta.tabId,
    tabTitle: tabMeta.tabTitle ?? doc.title ?? 'Tab EMR',
    origin,
    url: tabMeta.url ?? doc.location?.href ?? '',
    schemaHash,
    uniqueFields,
    fieldPairs,
    sections,
  }
}

/**
 * Hàm tự chứa tiêm vào tab trình duyệt qua `chrome.scripting.executeScript`.
 */
export function injectedTabDomSnapshot(tabId: number): RawTabExtraction {
  const fold = (input: string): string =>
    input
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[đĐ]/g, 'd')
      .toLowerCase()
      .replace(/[\s_:./-]+/g, ' ')
      .trim()

  const clean = (raw: string | null | undefined): string =>
    (raw ?? '').replace(/\s+/g, ' ').trim()

  const excludedSelector =
    'nav, header, footer, script, style, noscript, [id^="finding-"], [data-testid="ai-review-drawer"], [data-cdss-ignore="true"], [aria-label="Bốn chỉ số lâm sàng"]'

  const sidebarBlockLabels = new Set(['bhyt', 'di ung', 'chan doan'])
  const dynamicHeaderValueRe =
    /(?:\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b|@|\b0\d{11}\b|\b[A-Za-z]{2}\d{13}\b|\b\d{9}\b)/

  const isExcludedAside = (asideEl: Element): boolean => {
    if (asideEl.id && asideEl.id.startsWith('finding-')) return true
    if (asideEl.getAttribute('data-testid') === 'ai-review-drawer') return true
    const aria = fold(asideEl.getAttribute('aria-label') ?? '')
    if (!aria) return true
    return aria.includes('tham dinh') || aria.includes('tro ly ai') || aria.includes('nhan dinh')
  }

  const isExcluded = (el: Element): boolean => {
    if (el.closest(excludedSelector) !== null) return true
    const parentAside = el.closest('aside')
    if (parentAside !== null && isExcludedAside(parentAside)) return true
    if (el.id && el.id.startsWith('finding-')) return true
    const aria = fold(el.getAttribute('aria-label') ?? '')
    return (
      aria.includes('tham dinh') ||
      aria.includes('tro ly ai') ||
      aria.includes('nhan dinh') ||
      aria.includes('chi so lam sang')
    )
  }

  const inferBucket = (title: string): ExtractedSection['bucket'] => {
    const f = fold(title)
    if (
      f.includes('xet nghiem') ||
      f.includes('sinh hieu') ||
      f.includes('can lam sang') ||
      f.includes('vi sinh')
    ) {
      return 'labs_vitals'
    }
    if (
      f.includes('hanh chinh') ||
      f.includes('chan doan') ||
      f.includes('di ung') ||
      f.includes('co dia') ||
      f.includes('quan ly nguoi benh') ||
      f.includes('thanh ben')
    ) {
      return 'demographics_dx'
    }
    if (
      f.includes('y lenh') ||
      f.includes('thuoc') ||
      f.includes('dien bien') ||
      f.includes('phieu dieu tri') ||
      f.includes('hoi chan')
    ) {
      return 'meds_notes'
    }
    return 'other'
  }

  const nearestTitle = (el: Element): string => {
    const details = el.closest('details')
    if (details) {
      const s = details.querySelector('summary')
      if (s && clean(s.textContent)) return clean(s.textContent)
    }
    const sec = el.closest('section')
    if (sec) {
      const aria = clean(sec.getAttribute('aria-label'))
      if (aria) return aria
      const h = sec.querySelector('h1, h2, h3, h4')
      if (h && clean(h.textContent)) return clean(h.textContent)
    }
    const aside = el.closest('aside')
    if (aside && !isExcludedAside(aside)) {
      return 'Thông tin người bệnh (Thanh bên)'
    }
    return 'Thông tin chung'
  }

  const fieldPairs: ExtractedFieldPair[] = []
  const seenPairKeys = new Set<string>()
  const sections: ExtractedSection[] = []
  const uniqueMap = new Map<string, SchemaFieldDescriptor>()

  const register = (
    label: string,
    kieu_dom: ExtractedFieldPair['domKind'],
    sectionTitle: string,
  ) => {
    const cleaned = label.replace(/[:：]\s*$/, '').trim()
    if (!cleaned || cleaned.length > 80 || dynamicHeaderValueRe.test(cleaned)) return
    const key = fold(cleaned)
    if (!uniqueMap.has(key)) {
      uniqueMap.set(key, { ten_nhan: cleaned, kieu_dom, ngu_canh_muc: sectionTitle.slice(0, 120) })
    }
  }

  const pushPair = (
    label: string,
    value: string,
    domKind: ExtractedFieldPair['domKind'],
    sectionTitle: string,
  ) => {
    const cleanLabel = label.replace(/[:：]\s*$/, '').trim()
    const cleanValue = value.trim()
    if (!cleanLabel || !cleanValue || cleanValue === '—' || cleanValue === '-') return
    register(cleanLabel, domKind, sectionTitle)
    const dedupKey = `${fold(cleanLabel)}=${fold(cleanValue)}`
    if (seenPairKeys.has(dedupKey)) return
    seenPairKeys.add(dedupKey)
    fieldPairs.push({ label: cleanLabel, value: cleanValue, domKind, sectionTitle })
  }

  for (const dt of Array.from(document.querySelectorAll('dt'))) {
    if (isExcluded(dt)) continue
    const dd = dt.nextElementSibling
    if (!dd || dd.tagName.toUpperCase() !== 'DD') continue
    pushPair(clean(dt.textContent), clean(dd.textContent), 'dt_dd', nearestTitle(dt))
  }

  for (const aside of Array.from(document.querySelectorAll('aside'))) {
    if (isExcludedAside(aside)) continue
    const sidebarTitle = 'Thông tin người bệnh (Thanh bên)'
    for (const h2 of Array.from(aside.querySelectorAll('h2'))) {
      if (isExcluded(h2)) continue
      const nameText = clean(h2.textContent)
      if (nameText) pushPair('Họ tên', nameText, 'colon_pair', sidebarTitle)
      const next = h2.nextElementSibling
      if (next && next.tagName.toUpperCase() === 'P' && !isExcluded(next)) {
        const subText = clean(next.textContent)
        if (subText) pushPair('Giới tính / Tuổi', subText, 'colon_pair', sidebarTitle)
      }
    }
    for (const span of Array.from(aside.querySelectorAll('span'))) {
      if (isExcluded(span)) continue
      const rawLabel = clean(span.textContent).replace(/[:：]\s*$/, '')
      if (!sidebarBlockLabels.has(fold(rawLabel))) continue
      const valueEl = span.nextElementSibling
      if (!valueEl || isExcluded(valueEl)) continue
      pushPair(rawLabel, clean(valueEl.textContent), 'colon_pair', sidebarTitle)
    }
  }

  const tables = Array.from(document.querySelectorAll('table'))
  tables.forEach((table, idx) => {
    if (isExcluded(table)) return
    const sectionTitle = nearestTitle(table)
    if (fold(sectionTitle).includes('tham dinh')) return
    const headers = Array.from(table.querySelectorAll('thead th, tr th')).map((th) =>
      clean(th.textContent),
    )
    headers.forEach((h) => {
      if (h) register(h, 'table_th', sectionTitle)
    })
    const rows = Array.from(table.querySelectorAll('tbody tr, tr'))
    const lines: string[] = headers.length > 0 ? [headers.join(' | ')] : []
    for (const row of rows) {
      const cells = Array.from(row.querySelectorAll('td')).map((td) => clean(td.textContent))
      if (cells.some(Boolean)) {
        lines.push(cells.join(' | '))
      }
    }
    if (lines.length > 1 || (headers.length === 0 && lines.length > 0)) {
      sections.push({
        title: `${sectionTitle} (Bảng ${idx + 1})`,
        bucket: inferBucket(sectionTitle),
        text: lines.join('\n'),
      })
    }
  })

  for (const el of Array.from(document.querySelectorAll('section[aria-label], details'))) {
    if (isExcluded(el)) continue
    const title =
      clean(el.getAttribute('aria-label')) ||
      clean(el.querySelector('summary')?.textContent) ||
      clean(el.querySelector('h2, h3, h4')?.textContent)
    if (!title || fold(title).includes('tham dinh')) continue
    const lines = Array.from(el.querySelectorAll('p, li'))
      .filter((node) => !isExcluded(node))
      .map((node) => clean(node.textContent))
      .filter((line) => line.length >= 4)
    if (lines.length > 0) {
      sections.push({ title, bucket: inferBucket(title), text: lines.join('\n') })
    }
  }

  const origin = window.location.origin
  const uniqueFields = Array.from(uniqueMap.values())
  const canonical = `${origin}|${[...new Set(uniqueFields.map((f) => fold(f.ten_nhan)))].sort().join('|')}`
  let h1 = 0xdeadbeef ^ canonical.length
  let h2 = 0x41c6ce57 ^ canonical.length
  for (let i = 0; i < canonical.length; i += 1) {
    const ch = canonical.charCodeAt(i)
    h1 = Math.imul(h1 ^ ch, 2654435761)
    h2 = Math.imul(h2 ^ ch, 1597334677)
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)
  const schemaHash = `sch_${(h2 >>> 0).toString(16).padStart(8, '0')}${(h1 >>> 0).toString(16).padStart(8, '0')}`

  return {
    tabId,
    tabTitle: document.title || 'Tab EMR',
    origin,
    url: window.location.href,
    schemaHash,
    uniqueFields,
    fieldPairs,
    sections,
  }
}
