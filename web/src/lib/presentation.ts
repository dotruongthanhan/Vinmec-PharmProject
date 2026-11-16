import type {
  ChiSo,
  NhanDinh,
  TrangThaiTraLoi,
  TrichDanTraLoi,
} from '../api/types.ts'

export interface ChatStatusPresentation {
  className: string
  label: string
}

export type CitationSegment =
  | { kind: 'text'; value: string }
  | { kind: 'citation'; label: string; citation: TrichDanTraLoi }

/** Chọn kiểu hiển thị theo trạng thái câu trả lời khung hỏi thêm. */
export function getChatStatusPresentation(
  trangThai: TrangThaiTraLoi,
): ChatStatusPresentation {
  switch (trangThai) {
    case 'chua_san_sang':
      return {
        className: 'chat-status-chua-san-sang',
        label: 'Chức năng hỏi thêm chưa sẵn sàng',
      }
    case 'khong_co_nguon':
      return {
        className: 'chat-status-khong-co-nguon',
        label: 'Không tìm thấy căn cứ trong kho nguồn hiện có',
      }
    case 'ngoai_pham_vi':
      return {
        className: 'chat-status-ngoai-pham-vi',
        label: 'Ngoài phạm vi ca đang mở',
      }
    case 'loi':
      return {
        className: 'chat-status-loi',
        label: 'Đã xảy ra lỗi khi xử lý câu hỏi',
      }
    case 'ok':
      return {
        className: 'chat-status-ok',
        label: 'Đã kiểm chứng nguồn',
      }
  }
}

/** Tìm đối tượng ChiSo theo khoá cong_thuc; trả undefined nếu không khớp. */
export function findMetricByFormula(
  chiSo: readonly ChiSo[],
  congThuc: string | null | undefined,
): ChiSo | undefined {
  if (!congThuc) {
    return undefined
  }
  return chiSo.find((item) => item.cong_thuc === congThuc)
}

/** Suy tìm ChiSo tương ứng với trích dẫn tính toán khi TraLoi.trich_dan chưa có cong_thuc. */
export function inferMetricFromCitation(
  chiSo: readonly ChiSo[],
  banGhiId: string | null,
  nhan: string,
): ChiSo | undefined {
  const byId = findMetricByFormula(chiSo, banGhiId)
  if (byId) {
    return byId
  }
  const lower = nhan.toLowerCase()
  if (lower.includes('crcl') || lower.includes('cockcroft')) {
    return findMetricByFormula(chiSo, 'cockcroft_gault')
  }
  if (lower.includes('egfr') || lower.includes('ckd-epi') || lower.includes('ckd_epi')) {
    return findMetricByFormula(chiSo, 'egfr_ckd_epi_2021')
  }
  if (lower.includes('bmi')) {
    return findMetricByFormula(chiSo, 'bmi')
  }
  if (lower.includes('bsa') || lower.includes('mosteller')) {
    return findMetricByFormula(chiSo, 'bsa_mosteller')
  }
  return undefined
}

/** Đưa các nhận định AI chưa kiểm chứng xuống dưới mọi nhận định đã kiểm chứng, giữ thứ tự tương đối. */
export function sortAttentionFindings(findings: readonly NhanDinh[]): NhanDinh[] {
  const verified: NhanDinh[] = []
  const unverified: NhanDinh[] = []
  for (const item of findings) {
    if (item.nguon_goc_ma === 'ai_chua_kiem_chung') {
      unverified.push(item)
    } else {
      verified.push(item)
    }
  }
  return [...verified, ...unverified]
}

/** Tách đoạn văn bản thuần có đánh dấu [n] thành các phần text an toàn và nút trích dẫn. */
export function parseCitationsInText(
  text: string,
  citations: readonly TrichDanTraLoi[],
): CitationSegment[] {
  if (citations.length === 0) {
    return [{ kind: 'text', value: text }]
  }
  const byNumber = new Map<number, TrichDanTraLoi>()
  for (const item of citations) {
    byNumber.set(item.so, item)
  }

  const segments: CitationSegment[] = []
  const pattern = /\[(\d+)\]/g
  let lastIndex = 0
  let match: RegExpExecArray | null = pattern.exec(text)

  while (match !== null) {
    const num = Number(match[1])
    const citation = byNumber.get(num)
    if (citation) {
      if (match.index > lastIndex) {
        segments.push({ kind: 'text', value: text.slice(lastIndex, match.index) })
      }
      segments.push({ kind: 'citation', label: match[0], citation })
      lastIndex = match.index + match[0].length
    }
    match = pattern.exec(text)
  }

  if (lastIndex < text.length) {
    segments.push({ kind: 'text', value: text.slice(lastIndex) })
  }

  return segments.length > 0 ? segments : [{ kind: 'text', value: text }]
}
