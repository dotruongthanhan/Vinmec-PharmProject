import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AdministrativeSections } from '../features/order-detail/AdministrativeSections'
import type { FullIdentity, PatientManagement } from '../api/types'
import { administrativeDate } from '../lib/displayFormat'

describe('hành chính bệnh án', () => {
  it('hiện từng ô riêng và họ tên viết hoa, không gộp cân nặng', () => {
    const identity: FullIdentity = {
      ho_ten: 'Nguyễn Văn 20', ngay_sinh: '2023-11-12', tuoi: 3, gioi_tinh: 'nam',
      can_nang_kg: 14, chieu_cao_cm: 95, dan_toc: 'Kinh', doi_tuong: 'bhyt',
      bhyt: { so_the: 'TE1000000000020', gia_tri_den: '2027-12-31' },
      dia_chi_text: '20, Hà Nội',
      nguoi_bao_tin: { ho_ten: 'Nguyễn Thị 20', quan_he: 'me', dien_thoai: '0900 000 020' },
      bo_me: { bo: { ho_ten: 'Nguyễn Văn 20', nghe_nghiep: 'Công nhân' },
        me: { ho_ten: 'Nguyễn Thị 20', nghe_nghiep: 'Nhân viên' } },
    }
    const html = renderToStaticMarkup(<AdministrativeSections identity={identity} />)
    for (const label of ['Họ tên', 'Ngày sinh', 'Tuổi', 'Giới tính', 'Cân nặng (kg)',
      'Chiều cao (cm)', 'Dân tộc', 'Ngoại kiều', 'Nghề nghiệp', 'Địa chỉ', 'Đối tượng',
      'Số thẻ BHYT', 'Hạn BHYT', 'Người nhà báo tin', 'Quan hệ', 'Số điện thoại',
      'Họ tên bố', 'Nghề nghiệp bố', 'Họ tên mẹ', 'Nghề nghiệp mẹ']) {
      expect(html).toContain(`<dt`)
      expect(html).toContain(label)
    }
    expect(html).toContain('NGUYỄN VĂN 20')
    expect(html).toContain('12/11/2023')
    expect(html).toContain('0900 000 020')
    expect(html).not.toContain('3 tuổi · 14')
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

  it('quản lý có ngày giờ, khoa, hình thức và mã; lịch sử mở được từng lần', () => {
    const management: PatientManagement = {
      dot_dieu_tri_id: 'DT-1', thoi_diem_bat_dau: '2026-11-12T10:00:00+07:00',
      hinh_thuc_vao: 'cap_cuu', so_giuong: 'G-1', so_luu_tru: 'LT-2026-00001',
      lich_su_khoa: [{ khoa: 'Cấp cứu' }, { khoa: 'Nhi' }],
    }
    const html = renderToStaticMarkup(<AdministrativeSections management={management}
      history={[{ ...management, thu_tu: 1, chan_doan_chinh: 'Viêm họng',
        y_lenh: [{ y_lenh_id: 'YL-1', thuoc: ['Paracetamol 140 mg'] }],
        phieu_dieu_tri: [{ noi_dung: 'Theo dõi giả lập' }] }]} />)
    expect(html).toContain('Cấp cứu → Nhi')
    expect(html).toContain('LT-2026-00001')
    expect(html).toContain('<details')
    expect(html).toContain('<summary')
    expect(html).toContain('Paracetamol 140 mg')
    expect(html).toContain('Theo dõi giả lập')
  })

  it('giữ các giá trị đã có trong demo cũ ở từng ô riêng', () => {
    const html = renderToStaticMarkup(<AdministrativeSections legacy={{
      gioi_tuoi: 'Nam, 45 tuổi', can_nang: '70 kg', vao_vien: '09/11/2026 14:00',
      nam_vien: '2 ngày', khoa: 'Tim mạch · Nội trú',
    }} />)
    for (const value of ['>Nam</dd>', '>45</dd>', '>70</dd>', '09/11/2026 14:00', '2 ngày', 'Tim mạch']) {
      expect(html).toContain(value)
    }
    expect(html).not.toContain('45 tuổi · 70 kg')
  })

  it('hiển thị ngày giờ Việt Nam qua ranh giới ngày, ngày sinh không bị đổi ngày', () => {
    expect(administrativeDate('2026-11-12')).toBe('12/11/2026')
    const value = administrativeDate('2026-11-12T23:30:00Z')
    expect(value).toContain('13/11/2026')
    expect(value).toContain('06:30')
    expect(administrativeDate('khong-phai-ngay')).toBe('Chưa ghi nhận')
  })
})
