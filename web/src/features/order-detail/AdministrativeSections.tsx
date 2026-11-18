import type { ReactNode } from 'react'
import type { EncounterHistory, FullIdentity, PatientManagement } from '@/api/types'
import { administrativeDate } from '@/lib/displayFormat'

const MISSING = 'Chưa ghi nhận'
const LABELS: Record<string, string> = {
  nam: 'Nam', nu: 'Nữ', bhyt: 'Bảo hiểm y tế', thu_phi: 'Thu phí', mien: 'Miễn', khac: 'Khác',
  tu_den: 'Tự đến', co_quan_y_te: 'Cơ quan y tế', cap_cuu: 'Cấp cứu',
  kham_benh: 'Khám bệnh', truc_tiep: 'Trực tiếp', ra_vien: 'Ra viện', xin_ve: 'Xin về',
  bo_ve: 'Bỏ về', dua_ve: 'Đưa về', chuyen_vien: 'Chuyển viện', bo: 'Bố', me: 'Mẹ',
}

function text(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === '' ? MISSING : String(value)
}

function label(value: string | null | undefined): string {
  return value ? LABELS[value] ?? value : MISSING
}

function Fields({ items }: { items: [string, string][] }) {
  return <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
    {items.map(([name, value]) => <div key={name} className="min-w-0 text-sm">
      <dt className="text-fg-subtle">{name}</dt>
      <dd className="mt-1 break-words font-medium text-fg tabular-nums">{value}</dd>
    </div>)}
  </dl>
}

function RecordSection({ title, children }: { title: string; children: ReactNode }) {
  return <details open className="rounded-md border border-line bg-surface p-4">
    <summary className="cursor-pointer rounded-sm text-base font-semibold text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">{title}</summary>
    <div className="mt-4">{children}</div>
  </details>
}

export function AdministrativeSections({ identity: a, management: m, history = [], legacy }: {
  identity?: FullIdentity | null
  management?: PatientManagement | null
  history?: EncounterHistory[]
  legacy?: { gioi_tuoi: string; can_nang: string; vao_vien: string; nam_vien?: string | null; khoa: string }
}) {
  const items: [string, string][] = [
    ['Họ tên', a?.ho_ten?.toLocaleUpperCase('vi-VN') || MISSING],
    ['Ngày sinh', administrativeDate(a?.ngay_sinh)],
    ['Tuổi', a?.tuoi != null ? text(a.tuoi) : legacy?.gioi_tuoi.match(/(\d+)\s*tuổi/i)?.[1] || MISSING],
    ['Giới tính', a?.gioi_tinh ? label(a.gioi_tinh) : legacy?.gioi_tuoi.match(/\b(Nam|Nữ)/i)?.[1] || MISSING],
    ['Cân nặng (kg)', a?.can_nang_kg != null ? text(a.can_nang_kg) : legacy?.can_nang.match(/(\d+(?:[.,]\d+)?)\s*kg/i)?.[1] || MISSING],
    ['Chiều cao (cm)', text(a?.chieu_cao_cm)], ['Dân tộc', text(a?.dan_toc)],
    ['Ngoại kiều', text(a?.ngoai_kieu)], ['Nghề nghiệp', text(a?.nghe_nghiep)],
    ['Địa chỉ', a?.dia_chi_text || Object.values(a?.dia_chi ?? {}).filter(Boolean).join(', ') || MISSING],
    ['Đối tượng', label(a?.doi_tuong)], ['Số thẻ BHYT', text(a?.bhyt?.so_the)],
    ['Hạn BHYT', administrativeDate(a?.bhyt?.gia_tri_den)],
    ['Người nhà báo tin', text(a?.nguoi_bao_tin?.ho_ten)],
    ['Quan hệ', label(a?.nguoi_bao_tin?.quan_he)], ['Số điện thoại', text(a?.nguoi_bao_tin?.dien_thoai)],
    ['Nhóm máu', text(a?.nhom_mau)],
  ]
  if (a?.tuoi != null && a.tuoi < 16) {
    items.push(['Họ tên bố', text(a.bo_me?.bo?.ho_ten)], ['Nghề nghiệp bố', text(a.bo_me?.bo?.nghe_nghiep)],
      ['Họ tên mẹ', text(a.bo_me?.me?.ho_ten)], ['Nghề nghiệp mẹ', text(a.bo_me?.me?.nghe_nghiep)])
  }
  return <>
    <RecordSection title="I. Hành chính"><Fields items={items} /></RecordSection>
    <RecordSection title="II. Quản lý người bệnh"><Fields items={[
      ['Vào viện', m?.thoi_diem_bat_dau ? administrativeDate(m.thoi_diem_bat_dau) : legacy?.vao_vien || MISSING], ['Hình thức vào', label(m?.hinh_thuc_vao)],
      ['Nơi giới thiệu', label(m?.noi_gioi_thieu)], ['Cơ sở chuyển đến', text(m?.tuyen_chuyen_den)],
      ['Vào khoa lúc', administrativeDate(m?.vao_khoa_luc)], ['Khoa điều trị', m?.khoa_dieu_tri || legacy?.khoa || MISSING],
      ['Chuyển khoa', m?.lich_su_khoa?.map((stay) => stay.khoa).join(' → ') || MISSING],
      ['Ra viện', administrativeDate(m?.thoi_diem_ket_thuc)], ['Hình thức ra viện', label(m?.ra_vien?.hinh_thuc)],
      ['Chuyển viện đến', text(m?.ra_vien?.chuyen_vien_den)], ['Lý do ra viện', text(m?.ra_vien?.ly_do)],
      ['Tổng số ngày điều trị', m?.so_ngay_dieu_tri != null ? text(m.so_ngay_dieu_tri) : legacy?.nam_vien || MISSING], ['Số giường', text(m?.so_giuong)],
      ['Số lưu trữ', text(m?.so_luu_tru)], ['Mã y tế', text(m?.ma_yt)],
      ['Bác sĩ điều trị', text(m?.bac_si_dieu_tri)],
    ]} /></RecordSection>
    <RecordSection title="Lịch sử vào viện">
      {history.length === 0 ? <p className="text-sm text-fg-subtle">{MISSING}</p> :
        <table className="w-full table-fixed text-left text-xs text-fg">
          <caption className="sr-only">Mọi lần vào viện; mở một lần để xem y lệnh và phiếu điều trị</caption>
          <thead><tr>{['Lần / Khoa', 'Vào / Ra', 'Hình thức vào / ra', 'Số ngày', 'Chẩn đoán chính / Chi tiết'].map((title) =>
            <th scope="col" key={title} className="break-words p-2 align-top text-fg-subtle">{title}</th>)}</tr></thead>
          <tbody>{history.map((entry, index) => <tr key={entry.dot_dieu_tri_id} className="border-t border-line">
            <td className="break-words p-2 align-top">{entry.thu_tu ?? index + 1}<br />{text(entry.khoa_dieu_tri)}</td>
            <td className="break-words p-2 align-top">{administrativeDate(entry.thoi_diem_bat_dau)}<br />{administrativeDate(entry.thoi_diem_ket_thuc)}</td>
            <td className="break-words p-2 align-top">{label(entry.hinh_thuc_vao)}<br />{label(entry.ra_vien?.hinh_thuc)}</td>
            <td className="break-words p-2 align-top tabular-nums">{text(entry.so_ngay_dieu_tri)}</td>
            <td className="break-words p-2 align-top">{text(entry.chan_doan_chinh)}
              <details className="mt-2"><summary className="cursor-pointer rounded-sm text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">Xem y lệnh / phiếu lần {entry.thu_tu ?? index + 1}</summary>
                <h3 className="mt-3 font-semibold">Y lệnh</h3>
                {entry.y_lenh?.length ? entry.y_lenh.map((order) => <div key={order.y_lenh_id} className="my-2">
                  <p>{order.y_lenh_id} · {administrativeDate(order.thoi_diem_ke)} · {label(order.trang_thai)}</p>
                  <ul className="list-inside list-disc">{order.thuoc?.map((drug, i) => <li key={i}>{drug}</li>)}</ul>
                </div>) : <p>{MISSING}</p>}
                <h3 className="mt-3 font-semibold">Phiếu điều trị</h3>
                {entry.phieu_dieu_tri?.length ? entry.phieu_dieu_tri.map((note, i) => <p key={i} className="my-2 whitespace-pre-wrap">{administrativeDate(note.thoi_diem_ghi)} · {note.noi_dung}</p>) : <p>{MISSING}</p>}
              </details>
            </td>
          </tr>)}</tbody>
        </table>}
    </RecordSection>
  </>
}
