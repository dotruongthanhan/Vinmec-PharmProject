import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { ChiTietCa } from '../api/types'
import { TooltipProvider } from '../components/ui/tooltip'
import { PatientSidebarCard } from '../features/sidebar/PatientSidebarCard'
import { SidebarNav } from '../features/sidebar/SidebarNav'

function makeSamplePatient(overrides?: Partial<ChiTietCa>): ChiTietCa {
  const base = MOCK_CASE_DETAILS['DEMO-02']
  return {
    ...base,
    dinh_danh_day_du: {
      ho_ten: 'Nguyễn Văn An',
      ngay_sinh: '1959-03-15',
      tuoi: 67,
      gioi_tinh: 'nam',
      can_nang_kg: 62.5,
      chieu_cao_cm: 168,
      bhyt: {
        so_the: 'DN4010123456789',
        gia_tri_den: '2026-12-31',
      },
      nguoi_bao_tin: {
        ho_ten: 'Trần Thị Bình',
        quan_he: 'Vợ',
        dien_thoai: '0901234567',
      },
      dia_chi_text: 'Số 10 Đường Kiểm Thử, Hà Nội',
    },
    tom_tat: {
      ...base.tom_tat,
      chan_doan: [
        { loai_nhan: 'Phụ', noi_dung: 'Tăng huyết áp nguyên phát', ma_icd10: 'I10' },
        { loai_nhan: 'Chính', noi_dung: 'Viêm phổi cộng đồng', ma_icd10: 'J18.9' },
      ],
    },
    ...overrides,
  }
}

function renderSidebar({
  collapsed,
  inDrawer = false,
  patient,
}: {
  collapsed: boolean
  inDrawer?: boolean
  patient?: ChiTietCa | null
}): string {
  return renderToStaticMarkup(
    <TooltipProvider>
      <MemoryRouter>
        <SidebarNav
          collapsed={collapsed}
          inDrawer={inDrawer}
          activeSection="orders"
          onNavigate={vi.fn()}
          userEmail="duocsi@example.invalid"
          vaiTro="admin"
          isDemoMode={false}
          onToggleCollapse={vi.fn()}
          onOpenSettings={vi.fn()}
          onSignIn={vi.fn()}
          onSignOut={vi.fn()}
          patient={patient}
          onOpenEvidence={vi.fn()}
        />
      </MemoryRouter>
    </TooltipProvider>,
  )
}

describe('PatientSidebarCard và thanh bên hai nửa', () => {
  it('có patient → hiện họ tên in hoa, mã hồ sơ, số BHYT, chẩn đoán chính trước kèm ICD, 4 nhãn BMI/BSA/CrCl/eGFR', () => {
    const patient = makeSamplePatient()
    const html = renderToStaticMarkup(
      <PatientSidebarCard detail={patient} onOpenEvidence={vi.fn()} />,
    )

    expect(html).toContain('NGUYỄN VĂN AN')
    expect(html).toContain('Nam · 67 tuổi')
    expect(html).toContain('DEMO-02')
    expect(html).toContain('15/03/1959')
    expect(html).toContain('62,5 kg')
    expect(html).toContain('168 cm')
    expect(html).toContain('DN4010123456789')
    expect(html).toContain('hạn')
    expect(html).toContain('31/12/2026')
    expect(html).toContain('Viêm phổi cộng đồng')
    expect(html).toContain('(J18.9)')
    expect(html).toContain('Tăng huyết áp nguyên phát')
    expect(html).toContain('(I10)')
    expect(html.indexOf('Viêm phổi cộng đồng')).toBeLessThan(html.indexOf('Tăng huyết áp nguyên phát'))

    expect(html).toContain('BMI')
    expect(html).toContain('BSA')
    expect(html).toContain('CrCl')
    expect(html).toContain('eGFR')
    expect(html).toContain('16,0')
    expect(html).toContain('border-danger-line')

    // Không hiển thị thêm định danh nhạy cảm (SĐT người báo tin, địa chỉ)
    expect(html).not.toContain('0901234567')
    expect(html).not.toContain('Số 10 Đường Kiểm Thử')
  })

  it('thiếu trường → hiển thị "Chưa ghi nhận", không vỡ', () => {
    const base = MOCK_CASE_DETAILS['DEMO-02']
    const sparsePatient: ChiTietCa = {
      ...base,
      dinh_danh_day_du: null,
      dinh_danh: {
        ...base.dinh_danh,
        gioi_tuoi: '',
        can_nang: '',
        di_ung_text: '',
      },
      tom_tat: {
        ...base.tom_tat,
        chan_doan: [],
      },
      chi_so: [],
    }

    const html = renderToStaticMarkup(<PatientSidebarCard detail={sparsePatient} />)
    expect(html).toContain('Chưa ghi nhận')
    expect(html).toContain('BMI')
    expect(html).toContain('BSA')
    expect(html).toContain('CrCl')
    expect(html).toContain('eGFR')
    expect(html).toContain('—')
    expect(html).not.toContain('Xem thêm')
  })

  it('chẩn đoán > 3 → thu gọn còn 3 dòng đầu và có nút "Xem thêm" với aria-expanded="false"', () => {
    const patient = makeSamplePatient({
      tom_tat: {
        ...MOCK_CASE_DETAILS['DEMO-02'].tom_tat,
        chan_doan: [
          { loai_nhan: 'Phụ', noi_dung: 'Tăng huyết áp', ma_icd10: 'I10' },
          { loai_nhan: 'Phụ', noi_dung: 'Đái tháo đường typ 2', ma_icd10: 'E11' },
          { loai_nhan: 'Chính', noi_dung: 'Viêm phổi nặng', ma_icd10: 'J18.9' },
          { loai_nhan: 'Phụ', noi_dung: 'Rối loạn lipid máu', ma_icd10: 'E78' },
          { loai_nhan: 'Phụ', noi_dung: 'Bệnh thận mạn giai đoạn 3', ma_icd10: 'N18.3' },
        ],
      },
    })

    const html = renderToStaticMarkup(<PatientSidebarCard detail={patient} />)
    expect(html).toContain('Viêm phổi nặng')
    expect(html).toContain('Tăng huyết áp')
    expect(html).toContain('Đái tháo đường typ 2')
    expect(html).not.toContain('Rối loạn lipid máu')
    expect(html).not.toContain('Bệnh thận mạn giai đoạn 3')
    expect(html).toMatch(/<button[^>]*aria-expanded="false"[^>]*>Xem thêm<\/button>/)
  })

  it('SidebarNav không có patient → không có vùng thẻ; có patient → hiện thẻ; collapsed → không có họ tên đầy đủ, có nút "Thông tin người bệnh"', () => {
    const patient = makeSamplePatient()

    const noPatientHtml = renderSidebar({ collapsed: false, patient: null })
    expect(noPatientHtml).toContain('Hồ sơ cần duyệt')
    expect(noPatientHtml).not.toContain('aria-label="Thông tin người bệnh"')
    expect(noPatientHtml).not.toContain('Bốn chỉ số lâm sàng')

    const expandedHtml = renderSidebar({ collapsed: false, patient })
    expect(expandedHtml).toContain('aria-label="Thông tin người bệnh"')
    expect(expandedHtml).toContain('NGUYỄN VĂN AN')
    expect(expandedHtml).toContain('DN4010123456789')

    const collapsedHtml = renderSidebar({ collapsed: true, patient })
    expect(collapsedHtml).not.toContain('NGUYỄN VĂN AN')
    expect(collapsedHtml).not.toContain('DN4010123456789')
    expect(collapsedHtml).toMatch(/<button[^>]*aria-label="Thông tin người bệnh"/)

    const drawerHtml = renderSidebar({ collapsed: true, inDrawer: true, patient })
    expect(drawerHtml).toContain('NGUYỄN VĂN AN')
    expect(drawerHtml).toContain('DN4010123456789')
  })
})
