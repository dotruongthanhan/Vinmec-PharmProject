import { FileText } from 'lucide-react'
import type { ChiTietCa } from '@/api/types'
import { EmptyState } from '@/components/ui/empty-state'
import { formatClinicalText, parseLeadingSymbolLabel } from '@/lib/displayFormat'
import { isOutpatientCase } from '@/lib/unifiedOrderLines'
import { InfoRows, NotesTable, SectionHeading } from './DetailSections'
import type { InfoItem } from './DetailSections'
import { TreatmentSheets } from './MedicalRecordSections'

const MISSING = 'Chưa ghi nhận'

function primaryDiagnosis(detail: ChiTietCa): string {
  const list = detail.tom_tat.chan_doan
  if (list.length === 0) {
    return MISSING
  }
  return list
    .map((cd) => `${cd.noi_dung}${cd.ma_icd10 ? ` (${cd.ma_icd10})` : ''}`)
    .join('; ')
}

function patientIdentityItems(detail: ChiTietCa): InfoItem[] {
  const full = detail.dinh_danh_day_du
  const gender =
    full?.gioi_tinh === 'nam'
      ? 'Nam'
      : full?.gioi_tinh === 'nu'
        ? 'Nữ'
        : (detail.dinh_danh.gioi_tuoi.match(/(Nam|Nữ)/i)?.[1] ?? MISSING)
  const age =
    full?.tuoi != null
      ? `${full.tuoi} tuổi`
      : (detail.dinh_danh.gioi_tuoi.match(/\d+\s*tuổi/i)?.[0] ?? MISSING)
  const num = (value: number | null | undefined, unit: string) =>
    value != null ? `${String(value).replace('.', ',')} ${unit}` : MISSING
  return [
    { label: 'Họ tên', value: full?.ho_ten ? full.ho_ten.toUpperCase() : MISSING },
    { label: 'Giới tính', value: gender },
    { label: 'Tuổi', value: age },
    { label: 'Cân nặng', value: full ? num(full.can_nang_kg, 'kg') : detail.dinh_danh.can_nang },
    { label: 'Chiều cao', value: num(full?.chieu_cao_cm, 'cm') },
  ]
}

function treatmentInfoItems(detail: ChiTietCa): InfoItem[] {
  const { dinh_danh, tom_tat } = detail
  const lengthOfStay = isOutpatientCase(detail)
    ? 'Không nằm viện'
    : tom_tat.nam_vien_text
      ? formatClinicalText(tom_tat.nam_vien_text)
      : 'Chưa ghi nhận'

  return [
    { label: 'Mã ca', value: detail.ca_id },
    ...patientIdentityItems(detail),
    { label: 'Khoa, loại hồ sơ', value: dinh_danh.khoa_loai },
    {
      label: 'Vào viện',
      value: tom_tat.vao_vien_text ? formatClinicalText(tom_tat.vao_vien_text) : MISSING,
    },
    {
      label: 'Thời gian nằm viện',
      value: lengthOfStay,
    },
    { label: 'Dị ứng', value: parseLeadingSymbolLabel(dinh_danh.di_ung_text).text },
    { label: 'Chẩn đoán', value: primaryDiagnosis(detail), wide: true },
  ]
}

export interface ProgressTabContentProps {
  detail: ChiTietCa
  onFollowOrder?: () => void
}

/** Tab Diễn biến hợp nhất: Thông tin điều trị + bảng Cập nhật diễn biến + toàn bộ Phiếu điều trị. */
export function ProgressTabContent({ detail, onFollowOrder }: ProgressTabContentProps) {
  const notes = detail.chi_tiet.dien_bien
  const sheets = detail.phieu_dieu_tri ?? []

  return (
    <div className="flex flex-col gap-7">
      <section aria-label="Thông tin người bệnh" className="flex flex-col gap-2.5">
        <SectionHeading title="Thông tin điều trị" />
        <InfoRows items={treatmentInfoItems(detail)} />
      </section>

      <section aria-label="Cập nhật diễn biến" className="flex flex-col gap-2.5">
        <SectionHeading title="Cập nhật diễn biến" aside={`${notes.length} ghi nhận`} />
        {notes.length > 0 ? (
          <NotesTable notes={notes} />
        ) : (
          <div className="rounded-md border border-line bg-surface">
            <EmptyState
              icon={FileText}
              title="Chưa có ghi nhận diễn biến"
              description="Ca bệnh này chưa có ghi chép diễn biến lâm sàng."
            />
          </div>
        )}
      </section>

      {sheets.length > 0 ? (
        <section aria-label="Phiếu điều trị" className="flex flex-col gap-2.5">
          <SectionHeading title="Phiếu điều trị" aside={`${sheets.length} phiếu`} />
          <TreatmentSheets detail={detail} onFollowOrder={onFollowOrder} />
        </section>
      ) : null}
    </div>
  )
}
