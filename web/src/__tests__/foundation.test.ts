import {
  CircleCheck,
  CircleHelp,
  FileQuestion,
  Info,
  OctagonAlert,
  Scale,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { describe, expect, it } from 'vitest'
import { cn } from '@/lib/cn.ts'
import { parseLeadingSymbolLabel, parseTrendValue } from '@/lib/displayFormat.ts'
import {
  ICON_OF_TONE,
  iconOfAllergy,
  iconOfOrigin,
  toneOfAllergy,
  toneOfFinding,
  toneOfOrigin,
} from '@/lib/severity.ts'
import type { SemanticTone } from '@/lib/severity.ts'

describe('cn()', () => {
  it('gộp lớp điều kiện và ưu tiên lớp Tailwind đứng sau khi xung đột', () => {
    expect(cn('px-2 py-1', 'px-4')).toBe('py-1 px-4')
    expect(
      cn('text-sm', false, undefined, null, { hidden: false, 'font-medium': true }, ['text-fg']),
    ).toBe('text-sm font-medium text-fg')
  })

  it('không làm rụng lớp cỡ chữ tuỳ biến khi ghép cùng màu chữ', () => {
    expect(cn('text-metric text-fg')).toBe('text-metric text-fg')
    expect(cn('text-2xs text-fg-subtle')).toBe('text-2xs text-fg-subtle')
    expect(cn('text-md text-fg-muted')).toBe('text-md text-fg-muted')
    expect(cn('text-metric', 'text-sm')).toBe('text-sm')
  })
})

describe('severity.ts', () => {
  it('ánh xạ đủ mọi tổ hợp ket_luan_ma và muc_do_ma', () => {
    expect(toneOfFinding({ ket_luan_ma: 'can_xem', muc_do_ma: 'nghiem_trong' })).toBe('danger')
    expect(toneOfFinding({ ket_luan_ma: 'can_xem', muc_do_ma: 'can_luu_y' })).toBe('warning')
    expect(toneOfFinding({ ket_luan_ma: 'can_xem', muc_do_ma: null })).toBe('warning')
    expect(toneOfFinding({ ket_luan_ma: 'can_xem', muc_do_ma: 'muc_khac' })).toBe('warning')
    expect(toneOfFinding({ ket_luan_ma: 'khong_du_du_lieu', muc_do_ma: null })).toBe('missing')
    expect(toneOfFinding({ ket_luan_ma: 'khong_du_du_lieu', muc_do_ma: 'nghiem_trong' })).toBe(
      'missing',
    )
    expect(toneOfFinding({ ket_luan_ma: 'ngoai_hdsd', muc_do_ma: null })).toBe('offlabel')
    expect(toneOfFinding({ ket_luan_ma: 'ngoai_hdsd', muc_do_ma: 'can_luu_y' })).toBe('offlabel')
    expect(toneOfFinding({ ket_luan_ma: 'dat', muc_do_ma: null })).toBe('success')
    expect(toneOfFinding({ ket_luan_ma: 'dat', muc_do_ma: 'nghiem_trong' })).toBe('success')
  })

  it('trả về neutral cho mã kết luận lạ hoặc rỗng mà không ném lỗi', () => {
    expect(toneOfFinding({ ket_luan_ma: 'khong_xac_dinh', muc_do_ma: 'nghiem_trong' })).toBe(
      'neutral',
    )
    expect(toneOfFinding({ ket_luan_ma: '', muc_do_ma: null })).toBe('neutral')
    expect(toneOfFinding({ ket_luan_ma: null, muc_do_ma: undefined })).toBe('neutral')
  })

  it('ánh xạ toneOfOrigin cho luật, AI và mã lạ', () => {
    expect(toneOfOrigin('luat')).toBe('neutral')
    expect(toneOfOrigin('ai_da_kiem_chung')).toBe('ai')
    expect(toneOfOrigin('ai_chua_kiem_chung')).toBe('ai')
    expect(toneOfOrigin('nguon_la')).toBe('neutral')
    expect(toneOfOrigin(null)).toBe('neutral')
    expect(toneOfOrigin(undefined)).toBe('neutral')
  })

  it('ánh xạ toneOfAllergy cho 3 trạng thái dị ứng và mã lạ', () => {
    expect(toneOfAllergy('co_di_ung')).toBe('danger')
    expect(toneOfAllergy('khong_di_ung_da_hoi')).toBe('neutral')
    expect(toneOfAllergy('chua_co_thong_tin')).toBe('missing')
    expect(toneOfAllergy('khong_ro')).toBe('neutral')
    expect(toneOfAllergy(null)).toBe('neutral')
    expect(toneOfAllergy(undefined)).toBe('neutral')
  })

  it('ánh xạ đủ ICON_OF_TONE và biểu tượng nguồn gốc, dị ứng', () => {
    const expectedToneIcons: Record<SemanticTone, unknown> = {
      danger: OctagonAlert,
      warning: TriangleAlert,
      missing: CircleHelp,
      offlabel: FileQuestion,
      success: CircleCheck,
      ai: Sparkles,
      neutral: Info,
    }
    expect(ICON_OF_TONE).toEqual(expectedToneIcons)

    expect(iconOfOrigin('luat')).toBe(Scale)
    expect(iconOfOrigin('ai_da_kiem_chung')).toBe(Sparkles)
    expect(iconOfOrigin('ai_chua_kiem_chung')).toBe(Sparkles)
    expect(iconOfOrigin('khac')).toBe(Info)
    expect(iconOfOrigin(null)).toBe(Info)

    expect(iconOfAllergy('co_di_ung')).toBe(ShieldAlert)
    expect(iconOfAllergy('khong_di_ung_da_hoi')).toBe(ShieldCheck)
    expect(iconOfAllergy('chua_co_thong_tin')).toBe(ShieldQuestion)
    expect(iconOfAllergy('khac')).toBe(ShieldQuestion)
  })
})

describe('displayFormat.ts', () => {
  it('tách mũi tên lên/xuống cuối hoặc trong chuỗi ở parseTrendValue', () => {
    expect(parseTrendValue('212,0 \u25B2')).toEqual({ text: '212,0', direction: 'up' })
    expect(parseTrendValue('16,0 \u25BC')).toEqual({ text: '16,0', direction: 'down' })
    expect(parseTrendValue('212,0\u25B2')).toEqual({ text: '212,0', direction: 'up' })
    expect(parseTrendValue('212,0 \u25B2 umol/L')).toEqual({
      text: '212,0 umol/L',
      direction: 'up',
    })
    expect(parseTrendValue('15,0 \u25BC mg/dL')).toEqual({
      text: '15,0 mg/dL',
      direction: 'down',
    })
    expect(parseTrendValue('\u25BC')).toEqual({ text: '', direction: 'down' })
    expect(parseTrendValue('212,0')).toEqual({ text: '212,0', direction: null })
    expect(parseTrendValue('')).toEqual({ text: '', direction: null })
  })

  it('tách ký tự đầu nhãn API ở parseLeadingSymbolLabel', () => {
    expect(parseLeadingSymbolLabel('\u26A0 Có nhận định')).toEqual({
      text: 'Có nhận định',
      tone: 'warning',
    })
    expect(parseLeadingSymbolLabel('\u26A0 1 cần lưu ý')).toEqual({
      text: '1 cần lưu ý',
      tone: 'warning',
    })
    expect(parseLeadingSymbolLabel('\u2713 Đạt')).toEqual({
      text: 'Đạt',
      tone: 'success',
    })
    expect(parseLeadingSymbolLabel('\u26A0Không cách')).toEqual({
      text: 'Không cách',
      tone: 'warning',
    })
    expect(parseLeadingSymbolLabel('  \u2713  Đã xem')).toEqual({
      text: 'Đã xem',
      tone: 'success',
    })
    expect(parseLeadingSymbolLabel('1 nghiêm trọng')).toEqual({
      text: '1 nghiêm trọng',
      tone: null,
    })
    expect(parseLeadingSymbolLabel('Ghi chú \u26A0 giữa câu')).toEqual({
      text: 'Ghi chú \u26A0 giữa câu',
      tone: null,
    })
    expect(parseLeadingSymbolLabel('')).toEqual({ text: '', tone: null })
  })
})
