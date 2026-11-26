import { describe, expect, it } from 'vitest'
import { verifySamePatientAcrossTabs } from '../patientGuard'
import type { RawTabExtraction } from '../types'

function makeTab(tabId: number, url: string, pairs: Array<[string, string]>): RawTabExtraction {
  return {
    tabId,
    tabTitle: `Tab ${tabId}`,
    origin: 'http://localhost:5173',
    url,
    schemaHash: 'sch_1',
    uniqueFields: [],
    fieldPairs: pairs.map(([label, value]) => ({
      label,
      value,
      domKind: 'dt_dd',
      sectionTitle: 'I. Hành chính',
    })),
    sections: [],
  }
}

describe('patientGuard (kiểm tra khớp bệnh nhân giữa nhiều tab)', () => {
  it('cho phép khi cùng một mã y tế hoặc cùng ca trên URL', async () => {
    const tabA = makeTab(1, 'http://localhost:5173/app/y-lenh/DEMO-02?tab=hoso', [
      ['Mã y tế', 'YT-2026-062-01'],
    ])
    const tabB = makeTab(2, 'http://localhost:5173/app/y-lenh/DEMO-02?tab=xetnghiem', [
      ['Mã y tế', 'YT-2026-062-01'],
    ])
    const res = await verifySamePatientAcrossTabs([tabA, tabB])
    expect(res.status).toBe('MATCH')
  })

  it('cho phép cùng bệnh nhân HS-042 ngay cả khi 2 tab hiện tập trường khác nhau (Xét nghiệm vs Phiếu điều trị)', async () => {
    const tabLab = makeTab(1, 'http://localhost:5173/app/y-lenh/HS-042?tab=xet_nghiem', [
      ['Mã hồ sơ', 'HS-042'],
      ['Họ tên', 'NGUYỄN THỊ 42'],
      ['BHYT', 'GD4010000000042 hạn 31/12/2030'],
    ])
    const tabTreatment = makeTab(2, 'http://localhost:5173/app/y-lenh/HS-042?tab=phieu_dieu_tri', [
      ['Mã ca', 'HS-042'],
      ['Họ tên', 'NGUYỄN THỊ 42'],
      ['Mã y tế', 'YT-2026-042-01'],
    ])
    const res = await verifySamePatientAcrossTabs([tabLab, tabTreatment])
    expect(res.status).toBe('MATCH')
  })

  it('không báo lỗi giả khi 1 tab chỉ có URL ca và 1 tab có cả URL ca lẫn Họ tên', async () => {
    const tabUrlOnly = makeTab(1, 'http://localhost:5173/app/y-lenh/HS-042?tab=xet_nghiem', [])
    const tabWithName = makeTab(2, 'http://localhost:5173/app/y-lenh/HS-042?tab=phieu_dieu_tri', [
      ['Họ tên', 'NGUYỄN THỊ 42'],
      ['Mã ca', 'HS-042'],
    ])
    const res = await verifySamePatientAcrossTabs([tabUrlOnly, tabWithName])
    expect(res.status).toBe('MATCH')
  })

  it('chặn cứng khi chọn lẫn DEMO-02 và HS-024', async () => {
    const demo02 = makeTab(1, 'http://localhost:5173/app/y-lenh/DEMO-02', [
      ['Họ và tên', 'Nguyễn Thị Giả Lập A'],
    ])
    const hs024 = makeTab(2, 'http://localhost:5173/app/y-lenh/HS-024', [
      ['Họ và tên', 'Trần Văn Giả Lập B'],
    ])
    const res = await verifySamePatientAcrossTabs([demo02, hs024])
    expect(res.status).toBe('MISMATCH_BLOCKED')
  })
})
