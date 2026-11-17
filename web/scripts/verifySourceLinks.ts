/**
 * Kiểm tra liên kết nguồn trên dữ liệu thật: với mỗi nhãn DailyMed đã nạp, tải trang gốc một lần rồi xác nhận
 *   (a) điểm neo mục lớn `section-N` mà buildSourceLink sinh ra có tồn tại trên trang;
 *   (b) câu trích mô phỏng tìm thấy được trên trang theo cả hai đầu của text fragment, đúng thứ tự.
 *
 * Chạy (cần Node 22.6 trở lên, cần mạng):  node web/scripts/verifySourceLinks.ts [số nhãn tối đa]
 * Kết quả: bảng tóm tắt trên màn hình và báo cáo data/kb_reports/lien-ket-nguon.md.
 * Logic liên kết nằm ở web/src/lib/sourceLink.ts; bản ghi logic và cách sửa lỗi ở plan/TRACKING.md.
 */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { buildSourceLink, buildTextFragment, extractSectionNumber, majorSection, printerFriendlyUrl } from '../src/lib/sourceLink.ts'

interface Chunk {
  tai_lieu_id: string
  duong_dan_muc: string
  noi_dung_goc: string
  url_goc: string
  doan_trich_id: string
}

const ROOT = join(import.meta.dirname, '..', '..')
const CACHE = join(tmpdir(), 'dailymed-link-check')
mkdirSync(CACHE, { recursive: true })

const maxLabels = Number(process.argv[2] ?? Infinity)
const chunks: Chunk[] = readFileSync(join(ROOT, 'data/kb_curated/chunks.jsonl'), 'utf8')
  .split('\n')
  .filter(Boolean)
  .map((line) => JSON.parse(line) as Chunk)

const byLabel = new Map<string, Chunk[]>()
for (const chunk of chunks) {
  if (!chunk.url_goc.includes('dailymed.nlm.nih.gov')) continue
  byLabel.set(chunk.url_goc, [...(byLabel.get(chunk.url_goc) ?? []), chunk])
}

function decode(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, ' ')
    // Ranh giới khối (ô bảng, đoạn, mục danh sách, dòng): text fragment không khớp xuyên qua, nên đánh dấu riêng.
    .replace(/<\/(?:td|th|tr|p|li|div|h\d|caption)>|<br\s*\/?>/gi, ' \u0001 ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/\s+/g, ' ')
    .toLowerCase()
}

async function loadPage(url: string): Promise<string | null> {
  const file = join(CACHE, encodeURIComponent(url).slice(-120) + '.html')
  if (existsSync(file)) return readFileSync(file, 'utf8')
  const res = await fetch(url, { headers: { 'User-Agent': 'kb-link-check' } })
  if (!res.ok) return null
  const text = await res.text()
  writeFileSync(file, text)
  await new Promise((resolve) => setTimeout(resolve, 300))
  return text
}

/** Mô phỏng câu trích điển hình: đoạn 25 từ ở giữa đoạn nguồn (bỏ phần tiêu đề đầu đoạn). */
function sampleQuote(text: string): string {
  const words = text.split(/\s+/).filter(Boolean)
  return words.slice(Math.min(8, Math.max(0, words.length - 25)), 33).join(' ')
}

type Reason = 'ok' | 'neo_thieu' | 'khong_co_so_muc' | 'cau_khong_thay' | 'sai_thu_tu'
interface Row {
  chunk: Chunk
  section: string | null
  anchorOk: boolean | null
  fragment: Reason
}
const rows: Row[] = []
const pageProblems: string[] = []
let ambiguous = 0 // đoạn mở đầu của fragment xuất hiện nhiều lần trên trang: trình duyệt tô sáng lần đầu, có thể sai chỗ

let done = 0
for (const [url, labelChunks] of byLabel) {
  if (done >= maxLabels) break
  done++
  const html = await loadPage(printerFriendlyUrl(url)).catch(() => null)
  if (!html) {
    pageProblems.push(`${url}: không tải được trang`)
    continue
  }
  const text = decode(html)
  const anchors = new Set([...html.matchAll(/(?:name|id)="(section-[\d.]+)"/g)].map((m) => m[1]))
  for (const chunk of labelChunks) {
    const section = extractSectionNumber(chunk.duong_dan_muc)
    const anchorOk = section ? anchors.has(`section-${majorSection(section)}`) : null
    const quote = sampleQuote(chunk.noi_dung_goc)
    const fragment = buildTextFragment(quote)
    let reason: Reason = 'ok'
    if (fragment) {
      const [start, end = start] = decodeURIComponent(fragment.slice('text='.length))
        .toLowerCase()
        .split(/(?<!%2D),/)
      const si = text.indexOf(start.replace(/\s+/g, ' '))
      const ei = text.indexOf(end.replace(/\s+/g, ' '), Math.max(si, 0))
      if (si === -1 || ei === -1) reason = 'cau_khong_thay'
      else if (ei < si) reason = 'sai_thu_tu'
      else if (text.indexOf(start.replace(/\s+/g, ' '), si + 1) !== -1) ambiguous++
    }
    if (anchorOk === false) reason = reason === 'ok' ? 'neo_thieu' : reason
    if (anchorOk === null && reason === 'ok') reason = 'ok'
    rows.push({ chunk, section, anchorOk, fragment: reason })
    // gọi thử hàm ghép đầy đủ để bắt lỗi ngoại lệ
    buildSourceLink({ urlGoc: url, duongDanMuc: chunk.duong_dan_muc, trichNguyenVan: quote })
  }
}

const total = rows.length
const withSection = rows.filter((r) => r.section !== null)
const anchorHit = withSection.filter((r) => r.anchorOk).length
const fragHit = rows.filter((r) => r.fragment === 'ok' || r.fragment === 'neo_thieu').length
const bothOk = rows.filter((r) => r.fragment === 'ok').length
const pct = (a: number, b: number) => (b === 0 ? 'n/a' : `${((100 * a) / b).toFixed(1)}%`)

const fail = rows.filter((r) => r.fragment !== 'ok')
const byReason = new Map<Reason, Row[]>()
for (const r of fail) byReason.set(r.fragment, [...(byReason.get(r.fragment) ?? []), r])

const lines = [
  '# Kiểm tra liên kết nguồn DailyMed',
  '',
  `Chạy bằng web/scripts/verifySourceLinks.ts trên ${done} nhãn, ${total} đoạn nguồn.`,
  '',
  '| Chỉ số | Kết quả |',
  '| :--- | :--- |',
  `| Đoạn có số mục (sinh được neo) | ${withSection.length}/${total} (${pct(withSection.length, total)}) |`,
  `| Neo \`section-N\` có thật trên trang | ${anchorHit}/${withSection.length} (${pct(anchorHit, withSection.length)}) |`,
  `| Câu trích mô phỏng tìm thấy đủ hai đầu, đúng thứ tự | ${fragHit}/${total} (${pct(fragHit, total)}) |`,
  `| Đạt cả hai (neo đúng nếu có, và câu trích thấy) | ${bothOk}/${total} (${pct(bothOk, total)}) |`,
  `| Trong số tìm thấy, phần mở đầu xuất hiện nhiều lần trên trang (có thể tô sáng sai chỗ) | ${ambiguous}/${fragHit} (${pct(ambiguous, fragHit)}) |`,
  '',
  '## Lỗi theo nguyên nhân',
  '',
]
const LABEL: Record<Reason, string> = {
  ok: 'ok',
  neo_thieu: 'Neo mục không có trên trang (trang chưa đánh số kiểu section-N, hoặc đánh số lại)',
  khong_co_so_muc: 'Không suy ra được số mục',
  cau_khong_thay: 'Câu trích không tìm thấy trên trang (khác khoảng trắng, ký tự lạ, hoặc nằm trong bảng)',
  sai_thu_tu: 'Hai đầu câu trích tìm thấy nhưng sai thứ tự',
}
for (const [reason, list] of byReason) {
  lines.push(`### ${LABEL[reason]}: ${list.length}`, '')
  for (const r of list.slice(0, 15)) {
    lines.push(`- ${r.chunk.doan_trich_id} · ${r.chunk.duong_dan_muc}`)
  }
  if (list.length > 15) lines.push(`- … và ${list.length - 15} đoạn nữa`)
  lines.push('')
}
if (pageProblems.length > 0) {
  lines.push('## Trang không tải được', '', ...pageProblems.map((p) => `- ${p}`), '')
}
writeFileSync(join(ROOT, 'data/kb_reports/lien-ket-nguon.md'), lines.join('\n'))
console.log(lines.slice(0, 11).join('\n'))
