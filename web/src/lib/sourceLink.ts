/**
 * Ghép đường dẫn "Mở trang gốc" trỏ đúng mục và đúng câu trích trên trang nhãn DailyMed.
 * Ghi chú logic và cách sửa khi lỗi: plan/TRACKING.md, mục "Liên kết nguồn". Kiểm tra bằng web/scripts/verifySourceLinks.ts.
 *
 *  0. Trang nền: url_goc lưu dạng drugInfo.cfm?setid=X, nhưng trang này gấp các mục bằng display:none nên neo và
 *     text fragment đều không chạy. Ta mở bản nhãn đầy đủ fda/fdaDrugXsl.cfm?setid=X&type=display (xem printerFriendlyUrl).
 *  1. Neo theo mục lớn `#section-N` (N lấy từ duong_dan_muc, ví dụ "Warnings and Precautions > 5.4 ..." thành 5;
 *     mục cha không số như "Contraindications" đổi sang số chuẩn PLR). Không neo tiểu mục vì chỉ khoảng 82% nhãn có.
 *  2. Text fragment `:~:text=đầu,cuối`: trình duyệt cuộn tới và tô sáng đúng câu trích. Chỉ dùng đoạn văn xuôi dài nhất
 *     của câu trích (bỏ "|", ngoặc) vì chữ trong bảng và ngoặc trên trang khác chữ đã lưu.
 *
 * Mọi lớp chỉ thêm phần sau dấu #: sai thì trang vẫn mở bình thường. Nguồn không phải DailyMed giữ nguyên đường dẫn.
 */

const DAILYMED_HOST = 'dailymed.nlm.nih.gov'

/** Số mục chuẩn của nhãn PLR cho tiêu đề mục cha không đánh số. Khoá viết thường. */
const PLR_MAJOR_SECTIONS: Readonly<Record<string, string>> = {
  'indications and usage': '1',
  'dosage and administration': '2',
  'dosage forms and strengths': '3',
  contraindications: '4',
  'warnings and precautions': '5',
  'adverse reactions': '6',
  'drug interactions': '7',
  'use in specific populations': '8',
  'drug abuse and dependence': '9',
  overdosage: '10',
  description: '11',
  'clinical pharmacology': '12',
  'nonclinical toxicology': '13',
  'clinical studies': '14',
  'how supplied': '16',
}

/** Mục lớn của một số mục: "5.4" thành "5". */
export function majorSection(sectionNumber: string): string {
  return sectionNumber.split(".")[0]
}

/** Số từ giữ ở đầu và cuối câu trích khi tạo text fragment dạng khoảng. */
const FRAGMENT_EDGE_WORDS = 5

/** Lấy số mục ("5.4") từ đường dẫn mục của đoạn nguồn; không có thì thử bảng mục cha chuẩn. */
export function extractSectionNumber(duongDanMuc: string | null | undefined): string | null {
  if (!duongDanMuc) {
    return null
  }
  const parts = duongDanMuc.split('>').map((part) => part.trim())
  const last = parts[parts.length - 1] ?? ''
  const numbered = /^(\d{1,2}(?:\.\d{1,2}){0,3})\s+\S/.exec(last)
  if (numbered) {
    return numbered[1]
  }
  if (parts.length === 1) {
    return PLR_MAJOR_SECTIONS[last.toLowerCase()] ?? null
  }
  return null
}

function encodeFragmentText(text: string): string {
  // encodeURIComponent giữ lại "-", nhưng trong cú pháp text fragment "-" và "," có nghĩa riêng nên phải mã hoá.
  return encodeURIComponent(text).replace(/-/g, '%2D')
}

/** Ký tự mà chữ trên trang gốc thường khác chữ đã lưu (bảng ghi bằng "|", ngoặc kèm liên kết): không đặt vào fragment. */
const UNSTABLE_CHARS = /[|()[\]]/

/** Đoạn dài nhất của câu trích không chứa ký tự không ổn định, tính theo số từ. */
function longestStableRun(quote: string): string[] {
  let best: string[] = []
  for (const run of quote.split(UNSTABLE_CHARS)) {
    const words = run.split(/\s+/).filter(Boolean)
    if (words.length > best.length) {
      best = words
    }
  }
  return best
}

/**
 * Tạo phần `text=` từ câu trích: lấy đoạn dài nhất không chứa ký tự không ổn định;
 * ngắn thì dùng nguyên văn, dài thì dùng `đầu,cuối` của chính đoạn đó.
 * Trả null nếu không còn đoạn nào đủ 3 từ.
 */
export function buildTextFragment(quote: string | null | undefined): string | null {
  const words = longestStableRun(quote ?? '')
  if (words.length < 3) {
    return null
  }
  if (words.length <= FRAGMENT_EDGE_WORDS * 2) {
    return `text=${encodeFragmentText(words.join(' '))}`
  }
  const start = words.slice(0, FRAGMENT_EDGE_WORDS).join(' ')
  const end = words.slice(-FRAGMENT_EDGE_WORDS).join(' ')
  return `text=${encodeFragmentText(start)},${encodeFragmentText(end)}`
}

export interface SourceLinkInput {
  urlGoc: string | null | undefined
  duongDanMuc?: string | null
  trichNguyenVan?: string | null
}

/**
 * Trang nhãn mặc định của DailyMed (drugInfo.cfm) gấp mọi mục lại bằng display:none nên neo và text fragment
 * không hoạt động. Bản 'Official label (printer friendly)' hiển thị trọn nhãn, có neo cho cả tiểu mục.
 */
export function printerFriendlyUrl(urlGoc: string): URL | null {
  let url: URL
  try {
    url = new URL(urlGoc.trim())
  } catch {
    return null
  }
  const setId = url.searchParams.get('setid')
  if (url.protocol !== 'https:' || url.hostname !== DAILYMED_HOST || !setId) {
    return null
  }
  const full = new URL('/dailymed/fda/fdaDrugXsl.cfm', url.origin)
  full.searchParams.set('setid', setId)
  full.searchParams.set('type', 'display')
  return full
}

/**
 * Kiểm tra chuỗi URL và chỉ chấp nhận giao thức `https:`; trả về URL đã trim hoặc `null`.
 */
export function safeHttpsUrl(urlGoc: string | null | undefined): string | null {
  const trimmed = typeof urlGoc === 'string' ? urlGoc.trim() : ''
  if (!trimmed) {
    return null
  }
  let url: URL
  try {
    url = new URL(trimmed)
  } catch {
    return null
  }
  return url.protocol === 'https:' ? trimmed : null
}

/**
 * Trả URL HTTPS mở trang gốc; với nhãn DailyMed thì mở bản nhãn đầy đủ, kèm neo mục và text fragment.
 * Trả null nếu không phải địa chỉ HTTPS hợp lệ.
 */
export function buildSourceLink({
  urlGoc,
  duongDanMuc,
  trichNguyenVan,
}: SourceLinkInput): string | null {
  const trimmed = safeHttpsUrl(urlGoc)
  if (!trimmed) {
    return null
  }
  const full = printerFriendlyUrl(trimmed)
  if (!full) {
    return trimmed
  }
  const section = extractSectionNumber(duongDanMuc)
  const fragment = buildTextFragment(trichNguyenVan)
  const base = full.toString()
  if (!section && !fragment) {
    return base
  }
  const anchor = section ? `section-${majorSection(section)}` : ''
  return `${base}#${anchor}${fragment ? `:~:${fragment}` : ''}`
}
