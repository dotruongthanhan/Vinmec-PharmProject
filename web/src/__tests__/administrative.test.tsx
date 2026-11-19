import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { FullIdentity, PatientManagement } from '../api/types'
import { AdministrativeSections } from '../features/order-detail/AdministrativeSections'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'
import { PatientPinnedHeader } from '../features/order-detail/PatientPinnedHeader'
import { administrativeDate } from '../lib/displayFormat'
import { formatHistoryTime } from '../lib/historyTime'

describe('hành chính bệnh án và khung cố định người bệnh', () => {
  it('các mục I, II, III trong hồ sơ bệnh án mặc định thu gọn và hiển thị đúng trường yêu cầu', () => {
    const identity: FullIdentity = {
      ho_ten: 'Nguyễn Văn 20', ngay_sinh: '2023-11-12', tuoi: 3, gioi_tinh: 'nam',
      can_nang_kg: 14, chieu_cao_cm: 95, dan_toc: 'Kinh', ngoai_kieu: 'Việt Nam',
      nghe_nghiep: 'Trẻ em', cccd: '001202300020', dien_thoai: '0900 111 020',
      doi_tuong: 'bhyt',
      bhyt: { so_the: 'TE1000000000020', gia_tri_den: '2027-12-31' },
      dia_chi_text: '20, Hà Nội',
      nguoi_bao_tin: { ho_ten: 'Nguyễn Thị 20', quan_he: 'me', dien_thoai: '0900 000 020' },
      bo_me: {
        bo: { ho_ten: 'Nguyễn Văn 20', nghe_nghiep: 'Công nhân' },
        me: { ho_ten: 'Nguyễn Thị 20', nghe_nghiep: 'Nhân viên' },
      },
    }
    const html = renderToStaticMarkup(
      <AdministrativeSections
        identity={identity}
        diagnosisSection={<div>Nội dung chẩn đoán</div>}
      />,
    )
    expect(html).not.toMatch(/<details[^>]*\bopen\b/)
    for (const heading of ['I. Hành chính', 'II. Chẩn đoán', 'III. Quản lý người bệnh']) {
      expect(html).toContain(heading)
    }
    for (const label of [
      'Quốc tịch', 'Dân tộc', 'Nghề nghiệp', 'Địa chỉ', 'CCCD / Hộ chiếu',
      'Số điện thoại', 'Liên lạc khẩn cấp', 'Ward',
      'Họ tên bố', 'Nghề nghiệp bố', 'Họ tên mẹ', 'Nghề nghiệp mẹ',
    ]) {
      expect(html).toContain(`<dt`)
      expect(html).toContain(label)
    }
    expect(html).toContain('001202300020')
    expect(html).toContain('0900 111 020')
    expect(html).toContain('Nguyễn Thị 20 · Mẹ · 0900 000 020')
    expect(html).toContain('grid-cols-1')
    expect(html).toContain('sm:grid-cols-2')
  })

  it('ô thiếu có nhãn và nội dung Chưa ghi nhận; trẻ thiếu bố mẹ vẫn có ô', () => {
    const html = renderToStaticMarkup(<AdministrativeSections identity={{ tuoi: 3 }} />)
    expect(html).toContain('Chưa ghi nhận')
    expect(html).toContain('Họ tên bố')
    expect(html).toContain('Họ tên mẹ')
    expect(html).not.toContain('undefined')
    expect(html).not.toContain('null')
  })

  it('quản lý người bệnh hiện 1/ thông tin lần khám gần nhất và 2/ lịch sử các lần vào viện', () => {
    const management: PatientManagement = {
      dot_dieu_tri_id: 'DT-1', thoi_diem_bat_dau: '2026-11-12T10:00:00+07:00',
      hinh_thuc_vao: 'cap_cuu', so_giuong: 'G-1', so_luu_tru: 'LT-2026-00001',
      lich_su_khoa: [{ khoa: 'Cấp cứu' }, { khoa: 'Nhi' }],
    }
    const html = renderToStaticMarkup(<AdministrativeSections management={management}
      history={[{
        ...management, thu_tu: 1, chan_doan_chinh: 'Viêm họng',
        y_lenh: [{ y_lenh_id: 'YL-1', thuoc: ['Paracetamol 140 mg'] }],
        phieu_dieu_tri: [{ noi_dung: 'Theo dõi giả lập' }],
      }]} />)
    expect(html).toContain('1/ Thông tin lần khám gần nhất')
    expect(html).toContain('Ngày đến viện')
    expect(html).toContain('Ngày rời viện')
    expect(html).toContain('Lý do ra viện')
    expect(html).toContain('Khoa điều trị')
    expect(html).toContain('Lịch sử chuyển khoa, chuyển viện (nếu có)')
    expect(html).toContain('Cấp cứu → Nhi')
    expect(html).toContain('2/ Lịch sử các lần vào viện')
    expect(html).toContain('<details')
    expect(html).toContain('<summary')
    expect(html).toContain('Paracetamol 140 mg')
    expect(html).toContain('Theo dõi giả lập')
  })

  it('giữ các giá trị demo cũ cho ngày đến viện và khoa điều trị', () => {
    const html = renderToStaticMarkup(<AdministrativeSections legacy={{
      gioi_tuoi: 'Nam, 45 tuổi', can_nang: '70 kg', vao_vien: '09/11/2026 14:00',
      nam_vien: '2 ngày', khoa: 'Tim mạch · Nội trú',
    }} />)
    expect(html).toContain('09/11/2026 14:00')
    expect(html).toContain('Tim mạch · Nội trú')
  })

  it('khung cố định hiện đầy đủ thông tin bệnh nhân, chẩn đoán cạnh dị ứng/cơ địa và 4 chỉ số BMI/BSA/CrCl/eGFR', () => {
    const base = MOCK_CASE_DETAILS['DEMO-02']
    const detail = {
      ...base,
      dinh_danh_day_du: {
        ho_ten: 'Nguyễn Thị 62',
        ngay_sinh: '1951-05-10',
        tuoi: 75,
        gioi_tinh: 'nu' as const,
        can_nang_kg: 50,
        chieu_cao_cm: 155,
        nhom_mau: 'O',
        bhyt: { so_the: 'GD4010000000062', gia_tri_den: '2030-12-31' },
      },
    }
    const html = renderToStaticMarkup(
      <PatientPinnedHeader detail={detail} onOpenEvidence={() => {}} />,
    )
    expect(html).toContain('NGUYỄN THỊ 62')
    expect(html).toContain('10/05/1951')
    expect(html).toContain('75 tuổi')
    expect(html).toContain('Nữ')
    expect(html).toContain('50 kg')
    expect(html).toContain('155 cm')
    expect(html).toContain('GD4010000000062')
    expect(html).toContain('31/12/2030')
    expect(html).toContain('Nhóm máu:')
    expect(html).toContain('Chẩn đoán:')
    expect(html).toContain('Dị ứng / Cơ địa:')
    for (const metric of ['BMI', 'BSA', 'CrCl', 'eGFR']) {
      expect(html).toContain(`<span>${metric}</span>`)
    }
    // Chỉ hiện số liệu, không lặp tên công thức dài
    expect(html).not.toContain('Cockcroft-Gault')
    expect(html).not.toContain('CKD-EPI 2021')
  })

  it('OrderDetailView đặt khung cố định phía trên thanh thẻ và xóa bảng cận lâm sàng ngoài ngưỡng/diễn biến gần nhất khỏi thẻ Hồ sơ bệnh án', () => {
    const base = MOCK_CASE_DETAILS['DEMO-02']
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/app/y-lenh/DEMO-02?tab=ho_so_benh_an']}>
        <OrderDetailView
          detail={base}
          aiTrangThai="tat"
          aiKetQua={null}
          aiThoiGianMs={null}
          aiCanhBao={[]}
          sessionFeedbackForCase={{}}
          onRerunAi={() => {}}
          isFeedbackSubmitting={() => false}
          getFeedbackError={() => null}
          onSubmitFeedback={async () => true}
          onClearFeedbackError={() => {}}
          onOpenEvidence={() => {}}
          onAskAboutFinding={() => {}}
        />
      </MemoryRouter>,
    )
    const bannerIdx = html.indexOf('patient-pinned-header')
    const tablistIdx = html.indexOf('role="tablist"')
    expect(bannerIdx).toBeGreaterThan(-1)
    expect(tablistIdx).toBeGreaterThan(bannerIdx)
    expect(html).toContain('I. Hành chính')
    expect(html).toContain('II. Chẩn đoán')
    expect(html).toContain('III. Quản lý người bệnh')
    expect(html).not.toContain('Giá trị cận lâm sàng ngoài ngưỡng')
    expect(html).not.toContain('Diễn biến gần nhất')
    expect(html).not.toContain('Chỉ số lâm sàng tính từ hồ sơ')
  })

  it('hiển thị ngày giờ Việt Nam qua ranh giới ngày, ngày sinh không bị đổi ngày', () => {
    expect(administrativeDate('2026-11-12')).toBe('12/11/2026')
    const value = administrativeDate('2026-11-12T23:30:00Z')
    expect(value).toContain('13/11/2026')
    expect(value).toContain('06:30')
    expect(administrativeDate('khong-phai-ngay')).toBe('Chưa ghi nhận')
  })

  it.each(['2026-11-13T00:05+07:00', '2026-11-12T17:05Z', '2026-11-13T00:05', '2026-11-13 00:05'])(
    'hai định dạng cùng hiểu %s theo giờ Việt Nam',
    (value) => {
      expect(administrativeDate(value)).toMatch(/00:05.*13\/11\/2026/)
      expect(formatHistoryTime(value)).toMatch(/00:05.*13[-/]11/)
    },
  )

  it('hiện đang điều trị cho lần chưa kết thúc và giữ dữ liệu lần đã ra viện', () => {
    const current: PatientManagement = { dot_dieu_tri_id: 'DT-HIEN-TAI', so_ngay_dieu_tri: 2 }
    const html = renderToStaticMarkup(<AdministrativeSections management={current} history={[
      { ...current, thu_tu: 2 },
      {
        dot_dieu_tri_id: 'DT-CU', thu_tu: 1, thoi_diem_ket_thuc: '2026-11-13T00:05+07:00',
        ra_vien: { hinh_thuc: 'chuyen_vien' }, so_ngay_dieu_tri: 5,
      },
    ]} />)
    expect(html).toContain('Đang điều trị')
    expect(html).toContain('Đang điều trị · 2 ngày')
    expect(html).toContain('Không áp dụng')
    expect(html).toContain('Chuyển viện')
    expect(html).toContain('00:05')
  })
})
