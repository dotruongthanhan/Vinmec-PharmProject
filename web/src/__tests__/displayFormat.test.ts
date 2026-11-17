import { describe, expect, it } from 'vitest'
import {
  formatClinicalText,
  formatClinicalUnits,
  formatIsoTimestamp,
  formatWeightTypes,
} from '../lib/displayFormat.ts'

describe('định dạng hiển thị lâm sàng (displayFormat)', () => {
  it('định dạng thời điểm ISO có múi giờ sang HH:MM · DD/MM/YYYY', () => {
    expect(formatIsoTimestamp('2026-11-10T05:30:00+07:00')).toBe('05:30 · 10/11/2026')
    expect(formatIsoTimestamp('2026-11-09T22:30:00Z')).toBe('05:30 · 10/11/2026')
  })

  it('chuyển đổi đơn vị umol/L sang µmol/L', () => {
    expect(formatClinicalUnits('Creatinin máu: 212 umol/L')).toBe('Creatinin máu: 212 µmol/L')
  })

  it('chuyển đổi ba loại cân nặng sang tiếng Việt có dấu', () => {
    expect(formatWeightTypes('thuc_te · ly_tuong · hieu_chinh')).toBe(
      'thực tế · lý tưởng · hiệu chỉnh',
    )
  })

  it('dọn chuỗi thô gộp cả thời điểm ISO, đơn vị, cân nặng và dấu phẩy thập phân nhưng giữ mã ICD-10', () => {
    const raw =
      'Creatinin máu: 212.0 umol/L lúc 2026-11-10T05:30:00+07:00 (cân nặng thuc_te: 50.0 kg), chẩn đoán J18.9.'
    expect(formatClinicalText(raw)).toBe(
      'Creatinin máu: 212,0 µmol/L lúc 05:30 · 10/11/2026 (cân nặng thực tế: 50,0 kg), chẩn đoán J18.9.',
    )
  })
})
