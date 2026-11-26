import { describe, expect, it } from 'vitest'
import {
  dobToAgeYears,
  LocalDeidSession,
  restoreLocalLabels,
  sanitizeTabsForUpload,
  scrubText,
  shiftClinicalDates,
} from '../deidScrubber'
import { classifyLocalBaseline } from '../schemaCache'
import type { RawTabExtraction } from '../types'

describe('deidScrubber parity with tests/deid/test_scrubber.py', () => {
  it.each([
    ['Liên hệ a.b@example.org', 'Liên hệ [EMAIL_1]', 'EMAIL'],
    ['Email test+deid@example.org', 'Email [EMAIL_1]', 'EMAIL'],
    ['Thẻ BHYT DN4010123456789', 'Thẻ BHYT [BHYT_1]', 'BHYT'],
    ['Thẻ dn4010123456789', 'Thẻ [BHYT_1]', 'BHYT'],
    ['CCCD 001099012345', 'CCCD [CCCD_1]', 'CCCD'],
    ['sđt 0912 345 678', 'sđt [SDT_1]', 'SDT'],
    ['sđt +84912345678', 'sđt [SDT_1]', 'SDT'],
    ['sđt 03.1234.5678', 'sđt [SDT_1]', 'SDT'],
    ['HN 123456789', 'HN [HN_1]', 'HN'],
    ['Vào viện 05/11/2026', 'Vào viện [NGAY_1]', 'NGAY'],
    ['Ngày 5/11', 'Ngày [NGAY_1]', 'NGAY'],
    ['BS Nguyễn Văn An', 'BS [TEN_1]', 'TEN'],
    ['BN Trần Thị Bình', 'BN [TEN_1]', 'TEN'],
    ['BN Nguye\u0302\u0303n Va\u0306n An', 'BN [TEN_1]', 'TEN'],
    ['BS:\u00a0Nguyễn Văn An', 'BS:\u00a0[TEN_1]', 'TEN'],
  ])('che định danh %s', (input, expected, kind) => {
    const res = scrubText(input)
    expect(res.van_ban).toBe(expected)
    expect(res.thay_the[0]?.loai).toBe(kind)
  })

  it.each([
    'Huyết áp 120/80 mmHg, creatinin 212 umol/L, K 4.5',
    'bệnh nhân sốt cao, ăn kém',
    'liều 1/2 viên; tỉ lệ 3/4',
    'mạch 123456789 mmHg',
    'BN Nam, 65 tuổi',
    'bệnh nhân Nữ 40 tuổi',
    'HBV DNA 123456789 IU/mL',
    'dùng 1/2 ống',
  ])('giữ nguyên số liệu lâm sàng: %s', (text) => {
    const res = scrubText(text)
    expect(res.van_ban).toBe(text)
    expect(res.thay_the).toHaveLength(0)
  })
})

describe('LocalDeidSession Lớp 1 & quy đổi ngày sinh -> tuổi', () => {
  it('quy đổi ngày sinh sang tuổi nguyên dương', () => {
    const ref = new Date(2026, 10, 25)
    expect(dobToAgeYears('15/03/1951', ref)).toBe(75)
    expect(dobToAgeYears('1951-12-20', ref)).toBe(74)
  })

  it('bắt và thay tên/mã PII bị cắt khi lặp lại trong diễn biến tự do (không phân biệt dấu)', () => {
    const tab: RawTabExtraction = {
      tabId: 1,
      tabTitle: 'Hồ sơ',
      origin: 'http://localhost:5173',
      url: 'http://localhost:5173/app/y-lenh/DEMO-02',
      schemaHash: 'sch_demo',
      uniqueFields: [
        { ten_nhan: 'Họ và tên', kieu_dom: 'dt_dd', ngu_canh_muc: 'I. Hành chính' },
        { ten_nhan: 'Ngày sinh', kieu_dom: 'dt_dd', ngu_canh_muc: 'I. Hành chính' },
        { ten_nhan: 'Số thẻ BHYT', kieu_dom: 'dt_dd', ngu_canh_muc: 'I. Hành chính' },
        { ten_nhan: 'Cân nặng', kieu_dom: 'dt_dd', ngu_canh_muc: 'I. Hành chính' },
      ],
      fieldPairs: [
        { label: 'Họ và tên', value: 'Nguyễn Thị Giả Lập', domKind: 'dt_dd', sectionTitle: 'I. Hành chính' },
        { label: 'Ngày sinh', value: '15/03/1951', domKind: 'dt_dd', sectionTitle: 'I. Hành chính' },
        { label: 'Số thẻ BHYT', value: 'DN4010123456789', domKind: 'dt_dd', sectionTitle: 'I. Hành chính' },
        { label: 'Cân nặng', value: '50 kg', domKind: 'dt_dd', sectionTitle: 'I. Hành chính' },
      ],
      sections: [
        {
          title: 'Diễn biến',
          bucket: 'meds_notes',
          text: 'Bà Nguyen Thi Gia Lap (thẻ DN4010123456789) nhập viện vì viêm phổi.',
        },
      ],
    }

    const classified = classifyLocalBaseline(tab.uniqueFields)
    const { sections, audit } = sanitizeTabsForUpload([tab], classified, new Date(2026, 10, 25))
    const joined = sections.map((s) => s.noi_dung).join('\n')

    expect(joined).not.toContain('Nguyễn Thị Giả Lập')
    expect(joined).not.toContain('Nguyen Thi Gia Lap')
    expect(joined).not.toContain('DN4010123456789')
    expect(joined).not.toContain('15/03/1951')
    expect(joined).toContain('75 tuổi')
    expect(joined).toContain('Cân nặng: 50 kg')
    expect(audit.knownValueRedactions).toBeGreaterThanOrEqual(1)

    const session = new LocalDeidSession()
    session.addKnownPii('Trần Văn Thử', 'TEN')
    expect(session.scrubAll('Mời hội chẩn tran van thu').text).not.toContain('tran van thu')
  })
})

describe('Relative Date Shifting (Ngày +0, Ngày +30, ...)', () => {
  it('tính đúng chênh lệch ngày dương lịch và bỏ qua ngày sinh / hạn BHYT khỏi mốc T0', () => {
    const { shifted, restoreMap } = shiftClinicalDates([
      'Ngày sinh: 02/12/1947 | BHYT GD4010000000042 hạn 31/12/2030',
      'Lần vào viện 1 · 02/12/2025; tái khám 01/01/2026; XN 26/09/2026 08:00; vào viện 10/11/2026 09:00',
    ])

    expect(Object.keys(restoreMap)).toHaveLength(4)
    expect(restoreMap['Ngày +0']).toBe('02/12/2025')
    expect(restoreMap['Ngày +30']).toBe('01/01/2026')
    expect(restoreMap['Ngày +298']).toBe('26/09/2026')
    expect(restoreMap['Ngày +343']).toBe('10/11/2026')

    // Ngày sinh và hạn BHYT không bị chọn làm T0 (giữ nguyên cho bộ che PII xử lý tiếp)
    expect(shifted[0]).toContain('02/12/1947')
    expect(shifted[0]).toContain('31/12/2030')

    expect(shifted[1]).toContain('Ngày +0')
    expect(shifted[1]).toContain('Ngày +30')
    expect(shifted[1]).toContain('Ngày +298 08:00')
    expect(shifted[1]).toContain('Ngày +343 09:00')

    expect(restoreLocalLabels('Xét nghiệm Ngày +298 và tái khám Ngày +30.', restoreMap)).toBe(
      'Xét nghiệm Ngày +298 (26/09/2026) và tái khám Ngày +30 (01/01/2026).',
    )
  })

  it('quy đổi mốc ngày lâm sàng đồng nhất trên nhiều tab trong sanitizeTabsForUpload', () => {
    const tabTreatment: RawTabExtraction = {
      tabId: 10,
      tabTitle: 'Phiếu điều trị',
      origin: 'http://localhost:5173',
      url: 'http://localhost:5173/app/y-lenh/YL-HS-042-04',
      schemaHash: 'sch_hs042',
      uniqueFields: [
        { ten_nhan: 'Họ tên', kieu_dom: 'dt_dd', ngu_canh_muc: 'Thông tin điều trị' },
        { ten_nhan: 'Ngày sinh', kieu_dom: 'dt_dd', ngu_canh_muc: 'Thông tin điều trị' },
        { ten_nhan: 'BHYT', kieu_dom: 'dt_dd', ngu_canh_muc: 'Thông tin điều trị' },
        { ten_nhan: 'Vào viện', kieu_dom: 'dt_dd', ngu_canh_muc: 'Thông tin điều trị' },
      ],
      fieldPairs: [
        { label: 'Họ tên', value: 'NGUYỄN THỊ 42', domKind: 'dt_dd', sectionTitle: 'Thông tin điều trị' },
        { label: 'Ngày sinh', value: '02/12/1947', domKind: 'dt_dd', sectionTitle: 'Thông tin điều trị' },
        { label: 'BHYT', value: 'GD4010000000042 hạn 31/12/2030', domKind: 'dt_dd', sectionTitle: 'Thông tin điều trị' },
        { label: 'Vào viện', value: '10/11/2026 09:00', domKind: 'dt_dd', sectionTitle: 'Thông tin điều trị' },
      ],
      sections: [
        {
          title: 'Phiếu điều trị',
          bucket: 'meds_notes',
          text: 'Lần vào viện 1 · 02/12/2025. Ngày điều trị 1 · 11:00 02/12/2025. Khám lại 01/01/2026.',
        },
      ],
    }

    const tabLab: RawTabExtraction = {
      tabId: 11,
      tabTitle: 'Xét nghiệm',
      origin: 'http://localhost:5173',
      url: 'http://localhost:5173/app/y-lenh/YL-HS-042-04',
      schemaHash: 'sch_hs042',
      uniqueFields: [],
      fieldPairs: [],
      sections: [
        {
          title: 'Kết quả xét nghiệm',
          bucket: 'labs_vitals',
          text: 'INR ngày 26/09/2026 08:00: 2,4 (2,0 - 3,0)',
        },
      ],
    }

    const classified = classifyLocalBaseline(tabTreatment.uniqueFields)
    const { sections, audit, restoreMap } = sanitizeTabsForUpload(
      [tabTreatment, tabLab],
      classified,
      new Date(2026, 10, 26),
    )
    const joined = sections.map((s) => s.noi_dung).join('\n')

    expect(audit.dateAnchorCount).toBe(4)
    expect(restoreMap['Ngày +0']).toBe('02/12/2025')
    expect(restoreMap['Ngày +30']).toBe('01/01/2026')
    expect(restoreMap['Ngày +298']).toBe('26/09/2026')
    expect(restoreMap['Ngày +343']).toBe('10/11/2026')

    // Ngày gốc và PII không được lọt vào payload gửi lên server
    expect(joined).not.toContain('02/12/1947')
    expect(joined).not.toContain('31/12/2030')
    expect(joined).not.toContain('02/12/2025')
    expect(joined).not.toContain('26/09/2026')
    expect(joined).not.toContain('10/11/2026')
    expect(joined).not.toContain('NGUYỄN THỊ 42')
    expect(joined).not.toContain('GD4010000000042')

    // Mốc tương đối được giữ nguyên để AI hiểu đúng khoảng cách thời gian lâm sàng
    expect(joined).toContain('Ngày +0')
    expect(joined).toContain('Ngày +30')
    expect(joined).toContain('Ngày +298 08:00')
    expect(joined).toContain('Ngày +343 09:00')
  })
})
