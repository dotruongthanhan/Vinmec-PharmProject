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
