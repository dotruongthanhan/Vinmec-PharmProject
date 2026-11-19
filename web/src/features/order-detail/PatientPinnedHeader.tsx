import { ArrowDown, CircleHelp } from 'lucide-react'
import { createElement } from 'react'
import type { ChiSo, ChiTietCa } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/cn'
import {
  administrativeDate,
  formatClinicalText,
  parseLeadingSymbolLabel,
  parseTrendValue,
} from '@/lib/displayFormat'
import { iconOfAllergy, toneOfAllergy } from '@/lib/severity'
import type { EvidenceTarget } from '@/lib/uiTypes'

export interface PatientPinnedHeaderProps {
  detail: ChiTietCa
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

const MISSING = 'Chưa ghi nhận'

const METRIC_ORDER: readonly { key: string; label: string }[] = [
  { key: 'bmi', label: 'BMI' },
  { key: 'bsa_mosteller', label: 'BSA' },
  { key: 'cockcroft_gault', label: 'CrCl' },
  { key: 'egfr_ckd_epi_2021', label: 'eGFR' },
]

function formatNumberUnit(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) {
    return MISSING
  }
  return `${String(value).replace('.', ',')} ${unit}`
}

function formatAllDiagnoses(detail: ChiTietCa): string {
  const list = detail.tom_tat.chan_doan
  if (list.length === 0) {
    return MISSING
  }
  return list
    .map((cd) => `${cd.noi_dung}${cd.ma_icd10 ? ` (${cd.ma_icd10})` : ''}`)
    .join('; ')
}

/** Khung thông tin lâm sàng người bệnh cố định phía trên thanh thẻ tài liệu. */
export function PatientPinnedHeader({ detail, onOpenEvidence }: PatientPinnedHeaderProps) {
  const full = detail.dinh_danh_day_du
  const { dinh_danh, tom_tat, chi_so } = detail

  const hoTen = full?.ho_ten?.trim() ? full.ho_ten.trim().toLocaleUpperCase('vi-VN') : MISSING
  const ngaySinh = administrativeDate(full?.ngay_sinh)
  const tuoi =
    full?.tuoi != null
      ? `${full.tuoi} tuổi`
      : (dinh_danh.gioi_tuoi.match(/\d+\s*tuổi/i)?.[0] ?? MISSING)
  const gioiTinh =
    full?.gioi_tinh === 'nam'
      ? 'Nam'
      : full?.gioi_tinh === 'nu'
        ? 'Nữ'
        : (dinh_danh.gioi_tuoi.match(/\b(Nam|Nữ)/i)?.[1] ?? MISSING)
  const canNang =
    full?.can_nang_kg != null
      ? formatNumberUnit(full.can_nang_kg, 'kg')
      : full
        ? MISSING
        : dinh_danh.can_nang || MISSING
  const chieuCao = formatNumberUnit(full?.chieu_cao_cm, 'cm')
  const soTheBhyt = full?.bhyt?.so_the?.trim() || MISSING
  const hanBhyt = administrativeDate(full?.bhyt?.gia_tri_den)
  const nhomMau = full?.nhom_mau?.trim() || null

  const allergyTone = toneOfAllergy(dinh_danh.di_ung_ma)
  const allergyIconEl = createElement(iconOfAllergy(dinh_danh.di_ung_ma), {
    className: 'size-3.5 shrink-0',
    strokeWidth: 1.75,
  })
  const allergyText = parseLeadingSymbolLabel(dinh_danh.di_ung_text).text
  const allergyVariant = dinh_danh.di_ung_ma === 'khong_di_ung_da_hoi' ? 'outline' : 'soft'

  const diagnosisText = formatAllDiagnoses(detail)

  const metricByFormula = new Map<string, ChiSo>(chi_so.map((m) => [m.cong_thuc, m]))
  const orderedMetrics = METRIC_ORDER.map((spec) => ({
    ...spec,
    metric: metricByFormula.get(spec.key) ?? null,
  }))

  return (
    <section
      aria-label="Thông tin người bệnh cố định"
      className="patient-pinned-header border-b border-line/80 bg-surface"
    >
      <div className="mx-auto grid w-full max-w-[1200px] grid-cols-1 gap-3 px-5 py-3 lg:grid-cols-[minmax(0,1fr)_272px] lg:items-center">
        {/* Khối trái: thông tin điều trị cốt lõi của người bệnh */}
        <div className="flex min-w-0 flex-col gap-2">
          {/* Dòng 1: Họ tên + nhân trắc + BHYT + nhóm máu (nếu có) */}
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs">
            <h1 className="text-sm font-semibold tracking-tight text-fg">{hoTen}</h1>
            <span className="text-fg-muted">
              <span className="text-fg-subtle">Ngày sinh: </span>
              <span className="font-mono font-medium text-fg tabular-nums">{ngaySinh}</span>
            </span>
            <span className="text-fg-muted">
              <span className="text-fg-subtle">Tuổi: </span>
              <span className="font-medium text-fg tabular-nums">{tuoi}</span>
            </span>
            <span className="text-fg-muted">
              <span className="text-fg-subtle">Giới tính: </span>
              <span className="font-medium text-fg">{gioiTinh}</span>
            </span>
            <span className="text-fg-muted">
              <span className="text-fg-subtle">Cân nặng: </span>
              <span className="font-mono font-medium text-fg tabular-nums">{canNang}</span>
            </span>
            <span className="text-fg-muted">
              <span className="text-fg-subtle">Chiều cao: </span>
              <span className="font-mono font-medium text-fg tabular-nums">{chieuCao}</span>
            </span>
            {nhomMau ? (
              <span className="text-fg-muted">
                <span className="text-fg-subtle">Nhóm máu: </span>
                <span className="font-mono font-semibold text-fg">{nhomMau}</span>
              </span>
            ) : null}
          </div>

          {/* Dòng 2: BHYT */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-muted">
            <span>
              <span className="text-fg-subtle">Số thẻ BHYT: </span>
              <span className="font-mono font-medium text-fg tabular-nums">{soTheBhyt}</span>
            </span>
            <span>
              <span className="text-fg-subtle">Hạn BHYT: </span>
              <span className="font-mono font-medium text-fg tabular-nums">{hanBhyt}</span>
            </span>
          </div>

          {/* Dòng 3: Chẩn đoán đặt ngay cạnh Dị ứng / Cơ địa */}
          <div className="grid grid-cols-1 gap-x-4 gap-y-1.5 border-t border-line/60 pt-1.5 md:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] md:items-start">
            <div className="min-w-0 text-xs leading-snug">
              <span className="text-fg-subtle">Chẩn đoán: </span>
              <span className="font-medium text-fg break-words">{diagnosisText}</span>
            </div>

            <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-xs">
              <span className="text-fg-subtle shrink-0">Dị ứng / Cơ địa:</span>
              <Badge
                tone={allergyTone}
                variant={allergyVariant}
                icon={allergyIconEl}
                className={cn(
                  'whitespace-normal text-left',
                  dinh_danh.di_ung_ma === 'co_di_ung' && 'font-semibold',
                  dinh_danh.di_ung_ma === 'chua_co_thong_tin' && 'border-dashed font-semibold',
                )}
              >
                {allergyText}
              </Badge>
              {tom_tat.co_dia.map((item) => (
                <Badge key={item} tone="warning" variant="soft" className="whitespace-normal text-left">
                  {item}
                </Badge>
              ))}
            </div>
          </div>
        </div>

        {/* Cột phải ngoài cùng: 4 chỉ số BMI, BSA, CrCl, eGFR (chỉ số liệu, không công thức) */}
        <div
          aria-label="Bốn chỉ số lâm sàng"
          className="grid grid-cols-2 gap-1.5 border-t border-line/70 pt-2 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-3"
        >
          {orderedMetrics.map(({ key, label, metric }) => {
            if (!metric) {
              return (
                <div
                  key={key}
                  className="flex flex-col justify-between rounded-sm border border-line bg-surface-muted/60 px-2.5 py-1.5 font-mono text-xs tabular-nums"
                >
                  <span className="text-2xs font-sans font-medium text-fg-subtle">{label}</span>
                  <span className="font-semibold text-fg-muted">—</span>
                </div>
              )
            }

            const isCrclAbnormal =
              metric.cong_thuc === 'cockcroft_gault' &&
              dinh_danh.crcl_bat_thuong &&
              metric.gia_tri_text !== '—'
            const isMissing = metric.thieu.length > 0 || metric.gia_tri_text === '—'
            const parsedVal = parseTrendValue(metric.gia_tri_text)
            const valueText = formatClinicalText(parsedVal.text)
            const unitText =
              metric.don_vi && metric.gia_tri_text !== '—'
                ? formatClinicalText(metric.don_vi)
                : ''

            return (
              <button
                key={key}
                type="button"
                onClick={(e) =>
                  onOpenEvidence(
                    {
                      kind: 'metric',
                      metric,
                      titleHint: `${metric.nhan}: ${metric.gia_tri_text} ${metric.don_vi}`.trim(),
                    },
                    e.currentTarget,
                  )
                }
                title={
                  isMissing && metric.thieu.length > 0
                    ? `Thiếu: ${metric.thieu.join(', ')}`
                    : `Bấm để xem chi tiết ${label}`
                }
                className={cn(
                  'flex cursor-pointer flex-col justify-between rounded-sm border px-2.5 py-1.5 text-left transition-colors duration-120',
                  isCrclAbnormal
                    ? 'border-danger-line bg-danger-bg/80 text-danger-fg hover:bg-danger-bg'
                    : isMissing
                      ? 'border-missing-line bg-missing-bg/70 text-missing-fg hover:bg-missing-bg'
                      : 'border-line bg-surface-muted/40 text-fg hover:border-line-strong hover:bg-surface-hover',
                )}
              >
                <span className="flex items-center justify-between gap-1 text-2xs font-medium text-fg-subtle">
                  <span>{label}</span>
                  {isCrclAbnormal ? (
                    <ArrowDown className="size-3 shrink-0 text-danger-fg" strokeWidth={2} aria-hidden="true" />
                  ) : isMissing ? (
                    <CircleHelp className="size-3 shrink-0 text-missing-fg" strokeWidth={1.75} aria-hidden="true" />
                  ) : null}
                </span>
                <span className="mt-0.5 flex flex-wrap items-baseline gap-1 font-mono text-xs tabular-nums leading-tight">
                  <span className="font-semibold">{valueText}</span>
                  {unitText ? <span className="text-2xs text-fg-subtle">{unitText}</span> : null}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
