import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { MOCK_CASE_DETAILS } from '../api/mockData'
import type { FullIdentity, PatientManagement } from '../api/types'
import { AdministrativeSections } from '../features/order-detail/AdministrativeSections'
import { OrderDetailView } from '../features/order-detail/OrderDetailView'
import { administrativeDate } from '../lib/displayFormat'
import { formatHistoryTime } from '../lib/historyTime'

describe('hành chính bệnh án', () => {
  it('3 khối I, II, III mặc định thu gọn, giữ đủ trường hành chính local, gộp liên lạc khẩn cấp và thêm Khoa / giường', () => {
    const identity: FullIdentity = {
      ho_ten: 'Nguyễn Văn 20',
      ngay_sinh: '2023-11-12',
      tuoi: 3,
      gioi_tinh: 'nam',
      can_nang_kg: 14,
      chieu_cao_cm: 95,
      dan_toc: 'Kinh',
      ngoai_kieu: 'Việt Nam',
      nghe_nghiep: 'Trẻ em',
      doi_tuong: 'bhyt',
      bhyt: { so_the: 'TE1000000000020', gia_tri_den: '2027-12-31' },
      nhom_mau: 'O',
      dia_chi_text: '20, Hà Nội',
      nguoi_bao_tin: { ho_ten: 'Nguyễn Thị 20', quan_he: 'me', dien_thoai: '0900 000 020' },
      bo_me: {
        bo: { ho_ten: 'Nguyễn Văn 20', nghe_nghiep: 'Công nhân' },
        me: { ho_ten: 'Nguyễn Thị 20', nghe_nghiep: 'Nhân viên' },
      },
    }
    const management: PatientManagement = {
      dot_dieu_tri_id: 'DT-20',
      khoa_dieu_tri: 'Nhi',
      so_giuong: 'G-1',
    }
    const html = renderToStaticMarkup(
      <AdministrativeSections
        identity={identity}
        management={management}
        diagnosisSection={<div>Nội dung chẩn đoán</div>}
      />,
    )
    const disclosureTags = html.match(/<details\b[^>]*>/g) ?? []
    expect(disclosureTags).toHaveLength(3)
    expect(html).not.toMatch(/<details[^>]*\bopen\b/)
    for (const heading of ['I. Hành chính', 'II. Chẩn đoán', 'III. Quản lý người bệnh']) {
      expect(html).toContain(heading)
    }

    const block1 = html.slice(html.indexOf('I. Hành chính'), html.indexOf('II. Chẩn đoán'))
    for (const label of [
      'Họ tên',
      'Ngày sinh',
      'Tuổi',
      'Giới tính',
      'Cân nặng (kg)',
      'Chiều cao (cm)',
      'Dân tộc',
      'Ngoại kiều',
      'Nghề nghiệp',
      'Địa chỉ',
      'Đối tượng',
      'Số thẻ BHYT',
      'Hạn BHYT',
      'Nhóm máu',
      'Liên lạc khẩn cấp',
      'Khoa / giường',
      'Họ tên bố',
      'Nghề nghiệp bố',
      'Họ tên mẹ',
      'Nghề nghiệp mẹ',
    ]) {
      expect(block1).toContain('<dt')
      expect(block1).toContain(label)
    }
    expect(block1).toContain('NGUYỄN VĂN 20')
    expect(block1).toContain('12/11/2023')
    expect(block1).toContain('TE1000000000020')
    expect(block1).toContain('31/12/2027')
    expect(block1).toContain('>O</dd>')
    expect(block1).toContain('Nguyễn Thị 20 · Mẹ · 0900 000 020')
    expect(block1).toContain('Nhi · Giường G-1')
    expect(html).not.toContain('3 tuổi · 14')
    expect(html).not.toContain('Ward')
    expect(html).not.toContain('CCCD')
    expect(html).toContain('grid-cols-1')
    expect(html).toContain('sm:grid-cols-2')
  })

  it('ô thiếu có nhãn và nội dung Chưa ghi nhận; trẻ thiếu bố mẹ vẫn có ô; ẩn mục lịch sử khi rỗng', () => {
    const html = renderToStaticMarkup(<AdministrativeSections identity={{ tuoi: 3 }} />)
    expect(html).toContain('Chưa ghi nhận')
    expect(html).toContain('Họ tên bố')
    expect(html).toContain('Họ tên mẹ')
    expect(html).not.toContain('Lịch sử các lần vào viện')
    expect(html).not.toContain('undefined')
    expect(html).not.toContain('null')
  })

  it('quản lý người bệnh hiện 1/ thông tin lần khám gần nhất đủ trường và 2/ lịch sử các lần vào viện', () => {
    const management: PatientManagement = {
      dot_dieu_tri_id: 'DT-1',
      thoi_diem_bat_dau: '2026-11-12T10:00:00+07:00',
      vao_khoa_luc: '2026-11-12T10:15:00+07:00',
      hinh_thuc_vao: 'cap_cuu',
      noi_gioi_thieu: 'co_quan_y_te',
      tuyen_chuyen_den: 'BV Tuyến dưới',
      so_giuong: 'G-1',
      so_luu_tru: 'LT-2026-00001',
      ma_yt: 'YT-001',
      bac_si_dieu_tri: 'BS. Trần A',
      lich_su_khoa: [{ khoa: 'Cấp cứu' }, { khoa: 'Nhi' }],
    }
    const html = renderToStaticMarkup(
      <AdministrativeSections
        management={management}
        history={[
          {
            ...management,
            thu_tu: 1,
            chan_doan_chinh: 'Viêm họng',
            y_lenh: [{ y_lenh_id: 'YL-1', thuoc: ['Paracetamol 140 mg'] }],
            phieu_dieu_tri: [{ noi_dung: 'Theo dõi giả lập' }],
          },
        ]}
      />,
    )
    expect(html).toContain('1/ Thông tin lần khám gần nhất')
    for (const label of [
      'Ngày đến viện',
      'Ngày rời viện',
      'Hình thức vào',
      'Nơi giới thiệu',
      'Vào khoa lúc',
      'Lý do ra viện',
      'Tổng số ngày điều trị',
      'Số giường',
      'Số lưu trữ',
      'Mã y tế',
      'Bác sĩ điều trị',
      'Khoa điều trị',
      'Lịch sử chuyển khoa, chuyển viện (nếu có)',
    ]) {
      expect(html).toContain(label)
    }
    expect(html).toContain('Cơ quan y tế')
    expect(html).toContain('LT-2026-00001')
    expect(html).toContain('YT-001')
    expect(html).toContain('BS. Trần A')
    expect(html).toContain('<li>Cấp cứu</li>')
    expect(html).toContain('<li>Nhi</li>')
    expect(html).toContain('Chuyển khoa: Cấp cứu → Nhi · Chuyển đến từ: BV Tuyến dưới')
    expect(html).toContain('2/ Lịch sử các lần vào viện (1 lần)')
    expect(html).toContain('<details')
    expect(html).toContain('<summary')
    expect(html).toContain('Paracetamol 140 mg')
    expect(html).toContain('Theo dõi giả lập')
  })

  it('giữ các giá trị đã có trong demo cũ ở từng ô riêng', () => {
    const html = renderToStaticMarkup(
      <AdministrativeSections
        legacy={{
          gioi_tuoi: 'Nam, 45 tuổi',
          can_nang: '70 kg',
          vao_vien: '09/11/2026 14:00',
          nam_vien: '2 ngày',
          khoa: 'Tim mạch · Nội trú',
        }}
      />,
    )
    for (const value of [
      '>Nam</dd>',
      '>45</dd>',
      '>70</dd>',
      '09/11/2026 14:00',
      '2 ngày',
      '<li>Tim mạch · Nội trú</li>',
    ]) {
      expect(html).toContain(value)
    }
    expect(html).not.toContain('45 tuổi · 70 kg')
  })

  it('OrderDetailView gom tab Hồ sơ bệnh án thành 3 khối đóng, giữ chỉ số lâm sàng và bất thường bên ngoài', () => {
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
      tom_tat: {
        ...base.tom_tat,
        chan_doan: [
          { loai_nhan: 'Chính', noi_dung: 'Viêm phổi', ma_icd10: 'J18.9' },
          { loai_nhan: 'Kèm theo', noi_dung: 'Suy thận', ma_icd10: 'N18.4' },
        ],
        co_dia: ['Suy thận mạn'],
      },
      lich_su_vao_vien: [
        {
          dot_dieu_tri_id: 'DT-CU-01',
          thu_tu: 1,
          khoa_dieu_tri: 'Nội tổng hợp',
          thoi_diem_bat_dau: '2026-10-01T08:00:00+07:00',
          thoi_diem_ket_thuc: '2026-10-05T14:00:00+07:00',
          chan_doan_chinh: 'Viêm phế quản',
        },
      ],
    }

    const renderView = (targetDetail: typeof base) =>
      renderToStaticMarkup(
        <MemoryRouter initialEntries={['/app/y-lenh/DEMO-02?tab=ho_so_benh_an']}>
          <OrderDetailView
            detail={targetDetail}
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

    const htmlWithHistory = renderView(detail)
    const disclosureTags = htmlWithHistory.match(/<details\b[^>]*class="record-disclosure[^"]*"/g) ?? []
    expect(disclosureTags).toHaveLength(3)
    expect(htmlWithHistory).not.toMatch(/<details[^>]*\bopen\b/)
    expect(htmlWithHistory).not.toContain('III. Chẩn đoán')
    expect(htmlWithHistory).not.toContain('Ward')
    expect(htmlWithHistory).not.toContain('CCCD')

    const h1 = htmlWithHistory.indexOf('I. Hành chính')
    const h2 = htmlWithHistory.indexOf('II. Chẩn đoán')
    const h3 = htmlWithHistory.indexOf('III. Quản lý người bệnh')
    const lastDetailsClose = htmlWithHistory.lastIndexOf('</details>')
    const metricsIdx = htmlWithHistory.indexOf('Chỉ số lâm sàng tính từ hồ sơ')
    const abnormalIdx = htmlWithHistory.indexOf('Giá trị cận lâm sàng ngoài ngưỡng')

    expect(h1).toBeGreaterThan(-1)
    expect(h2).toBeGreaterThan(h1)
    expect(h3).toBeGreaterThan(h2)
    expect(lastDetailsClose).toBeGreaterThan(h3)
    expect(metricsIdx).toBeGreaterThan(lastDetailsClose)
    expect(abnormalIdx).toBeGreaterThan(metricsIdx)

    const block1 = htmlWithHistory.slice(h1, h2)
    expect(block1).toContain('NGUYỄN THỊ 62')
    expect(block1).toContain('GD4010000000062')
    expect(block1).toContain('Nhóm máu')
    expect(block1).toContain('>O</dd>')

    const block2 = htmlWithHistory.slice(h2, h3)
    expect(block2).toContain('Viêm phổi (J18.9); Suy thận (N18.4)')
    expect(block2).toContain('Dị ứng: đã hỏi, không ghi nhận')
    expect(block2).toContain('Cơ địa đặc biệt')
    expect(block2).toContain('Suy thận mạn')

    const block3 = htmlWithHistory.slice(h3, lastDetailsClose)
    expect(block3).toContain('Lịch sử các lần vào viện (1 lần)')

    const htmlWithoutHistory = renderView(base)
    expect(htmlWithoutHistory).toContain('I. Hành chính')
    expect(htmlWithoutHistory).toContain('II. Chẩn đoán')
    expect(htmlWithoutHistory).toContain('III. Quản lý người bệnh')
    expect(htmlWithoutHistory).not.toContain('Lịch sử các lần vào viện')
    expect(htmlWithoutHistory).toContain('Chỉ số lâm sàng tính từ hồ sơ')
    expect(htmlWithoutHistory).toContain('Giá trị cận lâm sàng ngoài ngưỡng')
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
    const html = renderToStaticMarkup(
      <AdministrativeSections
        management={current}
        history={[
          { ...current, thu_tu: 2 },
          {
            dot_dieu_tri_id: 'DT-CU',
            thu_tu: 1,
            thoi_diem_ket_thuc: '2026-11-13T00:05+07:00',
            ra_vien: { hinh_thuc: 'chuyen_vien' },
            so_ngay_dieu_tri: 5,
          },
        ]}
      />,
    )
    expect(html.match(/Đang điều trị/g)).toHaveLength(5)
    expect(html.match(/Đang điều trị · 2 ngày/g)).toHaveLength(2)
    expect(html.match(/Không áp dụng/g)).toHaveLength(1)
    expect(html).toContain('Chuyển viện')
    expect(html).toContain('00:05')
  })
})
