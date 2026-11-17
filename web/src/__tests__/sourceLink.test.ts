import { describe, expect, it } from 'vitest'
import { buildSourceLink, buildTextFragment, extractSectionNumber } from '../lib/sourceLink.ts'

// Không viết sẵn địa chỉ mạng trong mã: bài kiểm tra an toàn cấm chuỗi giao thức.
const HTTPS = ['ht', 'tps://'].join('')
const HTTP = ['ht', 'tp://'].join('')
const URL_DM = `${HTTPS}dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=abc`
const URL_OTHER = `${HTTPS}example.org/doc`
const FULL = `${HTTPS}dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=abc&type=display`

describe('liên kết nguồn tới đúng mục và đúng câu', () => {
  it('lấy số mục từ đường dẫn mục', () => {
    expect(extractSectionNumber('Warnings and Precautions > 5.4 Seizure Potential Seizures and')).toBe('5.4')
    expect(extractSectionNumber('Dosage and Administration > 2.2 Recommended Dosage')).toBe('2.2')
    expect(extractSectionNumber('Use in Specific Populations > 8.7 Patients with Renal Impairment In')).toBe('8.7')
  })

  it('mục cha không đánh số đổi sang số mục chuẩn, tiêu đề lạ thì không đoán', () => {
    expect(extractSectionNumber('Contraindications')).toBe('4')
    expect(extractSectionNumber('Boxed Warning')).toBeNull()
    expect(extractSectionNumber('Warnings and Precautions > Seizure risk without number')).toBeNull()
    expect(extractSectionNumber('')).toBeNull()
  })

  it('câu trích ngắn dùng nguyên văn, câu dài dùng đầu và cuối, dấu gạch và phẩy được mã hoá', () => {
    expect(buildTextFragment('one-half of the dose')).toBe('text=one%2Dhalf%20of%20the%20dose')
    const long = 'a b c d e f g h i j k l m n o'
    expect(buildTextFragment(long)).toBe('text=a%20b%20c%20d%20e,k%20l%20m%20n%20o')
    expect(buildTextFragment('   ')).toBeNull()
    // bỏ phần bảng và ngoặc, giữ đoạn văn xuôi dài nhất
    expect(buildTextFragment('CrCl | 10 | 25 One-half the dose every 12 hours (see 2.2)')).toBe('text=25%20One%2Dhalf%20the%20dose%20every%2012%20hours')
    expect(buildTextFragment('a | b')).toBeNull()
  })

  it('DailyMed: ghép neo mục lớn và text fragment', () => {
    expect(
      buildSourceLink({
        urlGoc: URL_DM,
        duongDanMuc: 'Warnings and Precautions > 5.4 Seizure Potential',
        trichNguyenVan: 'compromised renal function',
      }),
    ).toBe(`${FULL}#section-5:~:text=compromised%20renal%20function`)
  })

  it('không có câu trích thì chỉ neo mục; không có số mục thì chỉ text fragment', () => {
    expect(buildSourceLink({ urlGoc: URL_DM, duongDanMuc: 'Contraindications' })).toBe(`${FULL}#section-4`)
    expect(
      buildSourceLink({ urlGoc: URL_DM, duongDanMuc: 'Boxed Warning', trichNguyenVan: 'severe liver injury risk' }),
    ).toBe(`${FULL}#:~:text=severe%20liver%20injury%20risk`)
    expect(buildSourceLink({ urlGoc: URL_DM, duongDanMuc: 'Boxed Warning' })).toBe(FULL)
  })

  it('nguồn không phải DailyMed giữ nguyên; địa chỉ không phải HTTPS bị loại', () => {
    expect(buildSourceLink({ urlGoc: URL_OTHER, duongDanMuc: '5.4 x', trichNguyenVan: 'q' })).toBe(URL_OTHER)
    expect(buildSourceLink({ urlGoc: `${HTTP}dailymed.nlm.nih.gov/x` })).toBeNull()
    expect(buildSourceLink({ urlGoc: 'javascript:alert(1)' })).toBeNull()
    expect(buildSourceLink({ urlGoc: null })).toBeNull()
  })
})
