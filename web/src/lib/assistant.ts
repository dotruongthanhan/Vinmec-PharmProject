import type { ChiTietCa, NhanDinh, TrangThaiTraLoi } from '../api/types.ts'
import { extractShortDrugName } from './orderDetail.ts'

export const MAX_ASSISTANT_QUESTION_LENGTH = 1000
export const ASSISTANT_COUNTER_REMAINING_THRESHOLD = 100

export interface AssistantReplyGuardInput {
  requestCaseId: string
  activeCaseId: string | null
  requestSeq: number
  latestSeqForCase: number
  aborted: boolean
}

export interface AssistantInputStateInput {
  hasCase: boolean
  hoiThemEnabled: boolean
  lastStatus: TrangThaiTraLoi | null
  sending: boolean
  draft: string
}

export interface AssistantInputState {
  inputLocked: boolean
  lockMessage: string | null
  canSend: boolean
  showStop: boolean
  remainingChars: number
  showCharCounter: boolean
}

/**
 * Quyết định câu trả lời từ máy chủ có được phép ghi vào hội thoại ca hiện tại hay không.
 * Câu trả lời về muộn của ca cũ hoặc đã bị huỷ / quá hạn phải bị bỏ qua.
 */
export function shouldAcceptAssistantReply({
  requestCaseId,
  activeCaseId,
  requestSeq,
  latestSeqForCase,
  aborted,
}: AssistantReplyGuardInput): boolean {
  if (aborted) {
    return false
  }
  if (!activeCaseId || requestCaseId !== activeCaseId) {
    return false
  }
  return requestSeq === latestSeqForCase
}

/** Hàm thuần tính trạng thái khoá ô nhập, nút gửi/dừng và bộ đếm ký tự cho Trợ lý AI. */
export function getAssistantInputState({
  hasCase,
  hoiThemEnabled,
  lastStatus,
  sending,
  draft,
}: AssistantInputStateInput): AssistantInputState {
  const remainingChars = MAX_ASSISTANT_QUESTION_LENGTH - draft.length
  const showCharCounter = remainingChars < ASSISTANT_COUNTER_REMAINING_THRESHOLD

  if (!hasCase) {
    return {
      inputLocked: true,
      lockMessage: 'Mở một y lệnh để hỏi về ca đó.',
      canSend: false,
      showStop: false,
      remainingChars,
      showCharCounter: false,
    }
  }

  if (!hoiThemEnabled || lastStatus === 'chua_san_sang') {
    return {
      inputLocked: true,
      lockMessage: 'Máy chủ chưa bật trợ lý.',
      canSend: false,
      showStop: false,
      remainingChars,
      showCharCounter: false,
    }
  }

  const trimmed = draft.trim()
  const canSend = !sending && trimmed.length > 0 && draft.length <= MAX_ASSISTANT_QUESTION_LENGTH

  return {
    inputLocked: false,
    lockMessage: null,
    canSend,
    showStop: sending,
    remainingChars,
    showCharCounter,
  }
}

/** Sinh tối đa 3 câu hỏi gợi ý từ dữ liệu ca và nhận định cần xem đầu tiên. */
export function buildSuggestedQuestions(
  detail: ChiTietCa,
  attentionFindings: readonly NhanDinh[],
): string[] {
  const suggestions: string[] = []
  const seen = new Set<string>()

  const pushUnique = (q: string) => {
    const clean = q.trim()
    if (!clean || seen.has(clean) || suggestions.length >= 3) {
      return
    }
    seen.add(clean)
    suggestions.push(clean)
  }

  const firstAttention = attentionFindings[0]
  if (firstAttention && firstAttention.thuoc.trim()) {
    const shortDrug = extractShortDrugName(firstAttention.thuoc)
    if (shortDrug) {
      pushUnique(`Vì sao cần xem lại liều ${shortDrug}?`)
    }
  }

  for (const item of detail.cau_hoi_goi_y) {
    pushUnique(item)
    if (suggestions.length >= 3) {
      break
    }
  }

  return suggestions.slice(0, 3)
}
