import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import type { EncounterHistory, FullIdentity, PatientManagement } from '@/api/types'
import { administrativeDate } from '@/lib/displayFormat'

const MISSING = 'Chưa ghi nhận'
const ONGOING = 'Đang điều trị'
const NOT_APPLICABLE = 'Không áp dụng'
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

function dischargeFields(encounter?: PatientManagement | null, legacyDays?: string | null) {
  if (encounter && !encounter.thoi_diem_ket_thuc) {
    return {
      time: ONGOING, form: ONGOING, transfer: NOT_APPLICABLE, reason: NOT_APPLICABLE,
      days: encounter.so_ngay_dieu_tri == null ? ONGOING : `${ONGOING} · ${encounter.so_ngay_dieu_tri} ngày`,
    }
  }
  return {
    time: administrativeDate(encounter?.thoi_diem_ket_thuc),
    form: label(encounter?.ra_vien?.hinh_thuc),
    transfer: text(encounter?.ra_vien?.chuyen_vien_den),
    reason: text(encounter?.ra_vien?.ly_do ?? (encounter?.ra_vien?.hinh_thuc ? label(encounter.ra_vien.hinh_thuc) : null)),
    days: text(encounter?.so_ngay_dieu_tri ?? legacyDays),
  }
}

function formatEmergencyContact(contact?: FullIdentity['nguoi_bao_tin']): string {
  if (!contact) {
    return MISSING
  }
  const parts = [
    contact.ho_ten?.trim(),
    contact.quan_he ? label(contact.quan_he) : null,
    contact.dien_thoai?.trim(),
  ].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : MISSING
}

function formatWard(management?: PatientManagement | null, legacyKhoa?: string): string {
  const parts = [
    management?.khoa_dieu_tri?.trim() || legacyKhoa?.trim() || null,
    management?.so_giuong?.trim() ? `Giường ${management.so_giuong.trim()}` : null,
  ].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : MISSING
}

function departmentList(management?: PatientManagement | null, legacyKhoa?: string): string[] {
  const stays = management?.lich_su_khoa?.map((stay) => stay.khoa.trim()).filter(Boolean) ?? []
  const unique = Array.from(new Set(stays))
  if (unique.length > 0) {
    return unique
  }
  const fallback = management?.khoa_dieu_tri?.trim() || legacyKhoa?.trim()
  return fallback ? [fallback] : []
}

function formatTransferHistory(management?: PatientManagement | null): string {
  const segments: string[] = []
  const stays = management?.lich_su_khoa ?? []
  if (stays.length > 1) {
    segments.push(`Chuyển khoa: ${stays.map((stay) => stay.khoa).join(' → ')}`)
  }
  if (management?.tuyen_chuyen_den?.trim()) {
    segments.push(`Chuyển đến từ: ${management.tuyen_chuyen_den.trim()}`)
  }
  if (management?.ra_vien?.chuyen_vien_den?.trim()) {
    segments.push(`Chuyển viện đến: ${management.ra_vien.chuyen_vien_den.trim()}`)
  }
  return segments.length > 0 ? segments.join(' · ') : MISSING
}

export function Fields({ items }: { items: [string, string][] }) {
  return (
    <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {items.map(([name, value]) => (
        <div key={name} className="min-w-0 text-sm">
          <dt className="text-fg-subtle">{name}</dt>
          <dd className="mt-1 break-words font-medium text-fg tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Khối đóng/mở mặc định thu gọn dùng thẻ `<details>` nguyên bản theo chuẩn tiếp cận. */
export function RecordSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="record-disclosure rounded-md border border-line bg-surface">
      <summary className="record-disclosure-summary flex cursor-pointer items-center gap-2 rounded-md px-4 py-3 text-sm font-semibold text-fg transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
        <ChevronRight
          className="record-disclosure-chevron size-4 shrink-0 text-fg-subtle transition-transform duration-150"
          strokeWidth={2}
          aria-hidden="true"
        />
        <span>{title}</span>
      </summary>
      <div className="record-disclosure-body border-t border-line/70 px-4 py-4">{children}</div>
    </details>
  )
}

export function AdministrativeSections({
  identity: a,
  management: m,
  history = [],
  legacy,
  diagnosisSection,
}: {
  identity?: FullIdentity | null
  management?: PatientManagement | null
  history?: EncounterHistory[]
  legacy?: { gioi_tuoi: string; can_nang: string; vao_vien: string; nam_vien?: string | null; khoa: string }
  diagnosisSection?: ReactNode
}) {
  const discharge = dischargeFields(m, legacy?.nam_vien)
  const adminItems: [string, string][] = [
    ['Quốc tịch', text(a?.ngoai_kieu)],
    ['Dân tộc', text(a?.dan_toc)],
    ['Nghề nghiệp', text(a?.nghe_nghiep)],
    ['Địa chỉ', a?.dia_chi_text || Object.values(a?.dia_chi ?? {}).filter(Boolean).join(', ') || MISSING],
    ['CCCD / Hộ chiếu', text(a?.cccd)],
    ['Số điện thoại', text(a?.dien_thoai)],
    ['Liên lạc khẩn cấp', formatEmergencyContact(a?.nguoi_bao_tin)],
    ['Ward', formatWard(m, legacy?.khoa)],
  ]
  if (a?.tuoi != null && a.tuoi < 16) {
    adminItems.push(
      ['Họ tên bố', text(a.bo_me?.bo?.ho_ten)],
      ['Nghề nghiệp bố', text(a.bo_me?.bo?.nghe_nghiep)],
      ['Họ tên mẹ', text(a.bo_me?.me?.ho_ten)],
      ['Nghề nghiệp mẹ', text(a.bo_me?.me?.nghe_nghiep)],
    )
  }

  const depts = departmentList(m, legacy?.khoa)

  return (
    <>
      <RecordSection title="I. Hành chính">
        <Fields items={adminItems} />
      </RecordSection>

      {diagnosisSection ? (
        <RecordSection title="II. Chẩn đoán">{diagnosisSection}</RecordSection>
      ) : null}

      <RecordSection title="III. Quản lý người bệnh">
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
              1/ Thông tin lần khám gần nhất
            </p>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="min-w-0 text-sm">
                <dt className="text-fg-subtle">Ngày đến viện</dt>
                <dd className="mt-1 break-words font-medium text-fg tabular-nums">
                  {m?.thoi_diem_bat_dau
                    ? administrativeDate(m.thoi_diem_bat_dau)
                    : legacy?.vao_vien || MISSING}
                </dd>
              </div>
              <div className="min-w-0 text-sm">
                <dt className="text-fg-subtle">Ngày rời viện</dt>
                <dd className="mt-1 break-words font-medium text-fg tabular-nums">
                  {discharge.time}
                </dd>
              </div>
              <div className="min-w-0 text-sm">
                <dt className="text-fg-subtle">Lý do ra viện</dt>
                <dd className="mt-1 break-words font-medium text-fg">{discharge.reason}</dd>
              </div>
              <div className="min-w-0 text-sm">
                <dt className="text-fg-subtle">Khoa điều trị</dt>
                <dd className="mt-1 break-words font-medium text-fg">
                  {depts.length > 0 ? (
                    <ul className="list-inside list-disc space-y-0.5">
                      {depts.map((dept) => (
                        <li key={dept}>{dept}</li>
                      ))}
                    </ul>
                  ) : (
                    MISSING
                  )}
                </dd>
              </div>
              <div className="min-w-0 text-sm sm:col-span-2">
                <dt className="text-fg-subtle">Lịch sử chuyển khoa, chuyển viện (nếu có)</dt>
                <dd className="mt-1 break-words font-medium text-fg">
                  {formatTransferHistory(m)}
                </dd>
              </div>
            </dl>
          </div>

          {history.length > 0 ? (
            <div className="flex flex-col gap-2.5 border-t border-line/70 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
                2/ Lịch sử các lần vào viện ({history.length} lần)
              </p>
              <div className="overflow-x-auto">
                <table className="w-full table-fixed text-left text-xs text-fg">
                  <caption className="sr-only">
                    Mọi lần vào viện; mở một lần để xem y lệnh và phiếu điều trị
                  </caption>
                  <thead>
                    <tr>
                      {['Lần / Khoa', 'Vào / Ra', 'Hình thức vào / ra', 'Số ngày', 'Chẩn đoán chính / Chi tiết'].map(
                        (title) => (
                          <th
                            scope="col"
                            key={title}
                            className="break-words p-2 align-top text-fg-subtle"
                          >
                            {title}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((entry, index) => {
                      const entryDischarge = dischargeFields(entry)
                      return (
                        <tr key={entry.dot_dieu_tri_id} className="border-t border-line">
                          <td className="break-words p-2 align-top">
                            {entry.thu_tu ?? index + 1}
                            <br />
                            {text(entry.khoa_dieu_tri)}
                          </td>
                          <td className="break-words p-2 align-top">
                            {administrativeDate(entry.thoi_diem_bat_dau)}
                            <br />
                            {entryDischarge.time}
                          </td>
                          <td className="break-words p-2 align-top">
                            {label(entry.hinh_thuc_vao)}
                            <br />
                            {entryDischarge.form}
                          </td>
                          <td className="break-words p-2 align-top tabular-nums">
                            {entryDischarge.days}
                          </td>
                          <td className="break-words p-2 align-top">
                            {text(entry.chan_doan_chinh)}
                            <details className="mt-2">
                              <summary className="cursor-pointer rounded-sm text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
                                Xem y lệnh / phiếu lần {entry.thu_tu ?? index + 1}
                              </summary>
                              <p className="mt-3 font-semibold">Y lệnh</p>
                              {entry.y_lenh?.length ? (
                                entry.y_lenh.map((order) => (
                                  <div key={order.y_lenh_id} className="my-2">
                                    <p>
                                      {order.y_lenh_id} · {administrativeDate(order.thoi_diem_ke)} ·{' '}
                                      {label(order.trang_thai)}
                                    </p>
                                    <ul className="list-inside list-disc">
                                      {order.thuoc?.map((drug, i) => (
                                        <li key={i}>{drug}</li>
                                      ))}
                                    </ul>
                                  </div>
                                ))
                              ) : (
                                <p>{MISSING}</p>
                              )}
                              <p className="mt-3 font-semibold">Phiếu điều trị</p>
                              {entry.phieu_dieu_tri?.length ? (
                                entry.phieu_dieu_tri.map((note, i) => (
                                  <p key={i} className="my-2 whitespace-pre-wrap">
                                    {administrativeDate(note.thoi_diem_ghi)} · {note.noi_dung}
                                  </p>
                                ))
                              ) : (
                                <p>{MISSING}</p>
                              )}
                            </details>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      </RecordSection>
    </>
  )
}
