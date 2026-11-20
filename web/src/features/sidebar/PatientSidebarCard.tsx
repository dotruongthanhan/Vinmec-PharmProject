import { ArrowDown, CircleHelp, UserRound } from 'lucide-react'
import { createElement, useId, useState } from 'react'
import type { ChanDoanTomTat, ChiSo, ChiTietCa } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'
import {
  administrativeDate,
  formatClinicalText,
  parseLeadingSymbolLabel,
  parseTrendValue,
} from '@/lib/displayFormat'
import { iconOfAllergy, toneOfAllergy } from '@/lib/severity'
import type { EvidenceTarget } from '@/lib/uiTypes'

const MISSING = 'Chưa ghi nhận'
const MAX_VISIBLE_DIAGNOSES = 3

const METRIC_ORDER: readonly { key: string; label: string }[] = [
  { key: 'bmi', label: 'BMI' },
  { key: 'bsa_mosteller', label: 'BSA' },
  { key: 'cockcroft_gault', label: 'CrCl' },
  { key: 'egfr_ckd_epi_2021', label: 'eGFR' },
]

export interface PatientSidebarCardProps {
  detail: ChiTietCa
  onOpenEvidence?: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

export interface PatientCollapsedButtonProps {
  detail: ChiTietCa
  onExpand?: () => void
}

interface PatientSummary {
  hoTen: string
  genderAgeText: string
  maHoSo: string
  ngaySinh: string
  canNang: string
  chieuCao: string
  soTheBhyt: string | null
  hanBhyt: string
}

function formatNumberUnit(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return MISSING
  }
  return `${String(value).replace('.', ',')} ${unit}`
}

function normalizeGenderMatch(raw: string | undefined): string | null {
  if (!raw) {
    return null
  }
  return raw.toLowerCase() === 'nam' ? 'Nam' : 'Nữ'
}

function extractPatientSummary(detail: ChiTietCa): PatientSummary {
  const full = detail.dinh_danh_day_du
  const { dinh_danh } = detail

  const hoTen = full?.ho_ten?.trim() ? full.ho_ten.trim().toLocaleUpperCase('vi-VN') : MISSING
  const tuoi =
    full?.tuoi != null
      ? `${full.tuoi} tuổi`
      : (dinh_danh.gioi_tuoi.match(/\d+\s*tuổi/i)?.[0] ?? MISSING)
  const gioiTinh =
    full?.gioi_tinh === 'nam'
      ? 'Nam'
      : full?.gioi_tinh === 'nu'
        ? 'Nữ'
        : (normalizeGenderMatch(dinh_danh.gioi_tuoi.match(/\b(Nam|Nữ)/i)?.[1]) ?? MISSING)

  const genderAgeText =
    gioiTinh === MISSING && tuoi === MISSING ? MISSING : `${gioiTinh} · ${tuoi}`

  const maHoSo = detail.ca_id?.trim() || MISSING
  const ngaySinh = administrativeDate(full?.ngay_sinh)

  const rawFallbackWeight = dinh_danh.can_nang?.trim()
  const fallbackWeight =
    rawFallbackWeight && rawFallbackWeight !== '—'
      ? formatClinicalText(rawFallbackWeight)
      : MISSING
  const canNang =
    full?.can_nang_kg != null
      ? formatNumberUnit(full.can_nang_kg, 'kg')
      : full
        ? MISSING
        : fallbackWeight

  const chieuCao = formatNumberUnit(full?.chieu_cao_cm, 'cm')
  const soTheBhyt = full?.bhyt?.so_the?.trim() || null
  const hanBhyt = administrativeDate(full?.bhyt?.gia_tri_den)

  return {
    hoTen,
    genderAgeText,
    maHoSo,
    ngaySinh,
    canNang,
    chieuCao,
    soTheBhyt,
    hanBhyt,
  }
}

function isPrimaryDiagnosis(item: ChanDoanTomTat): boolean {
  return /chính/i.test(item.loai_nhan)
}

function sortDiagnosesPrimaryFirst(diagnoses: readonly ChanDoanTomTat[]): ChanDoanTomTat[] {
  const primary: ChanDoanTomTat[] = []
  const others: ChanDoanTomTat[] = []
  for (const item of diagnoses) {
    if (isPrimaryDiagnosis(item)) {
      primary.push(item)
    } else {
      others.push(item)
    }
  }
  return [...primary, ...others]
}

/** Nút biểu tượng khi thanh bên thu gọn; tooltip hiện họ tên in hoa và giới/tuổi. */
export function PatientCollapsedButton({ detail, onExpand }: PatientCollapsedButtonProps) {
  const { hoTen, genderAgeText } = extractPatientSummary(detail)
  const tooltipText =
    hoTen === MISSING
      ? genderAgeText === MISSING
        ? 'Thông tin người bệnh'
        : genderAgeText
      : genderAgeText === MISSING
        ? hoTen
        : `${hoTen} · ${genderAgeText}`

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Thông tin người bệnh"
          onClick={onExpand}
          className="flex h-9 w-full cursor-pointer items-center justify-center rounded-sm text-ink-muted transition-colors duration-120 hover:bg-ink-soft hover:text-ink-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <UserRound className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">{tooltipText}</TooltipContent>
    </Tooltip>
  )
}

/** Thẻ thông tin người bệnh đặt ở nửa dưới thanh bên trái khi đang mở một ca. */
export function PatientSidebarCard({ detail, onOpenEvidence }: PatientSidebarCardProps) {
  const [diagnosesExpanded, setDiagnosesExpanded] = useState(false)
  const diagnosisListId = useId()

  const summary = extractPatientSummary(detail)
  const { dinh_danh, tom_tat, chi_so } = detail

  const allergyTone = toneOfAllergy(dinh_danh.di_ung_ma)
  const allergyIconEl = createElement(iconOfAllergy(dinh_danh.di_ung_ma), {
    className: 'size-3.5 shrink-0',
    strokeWidth: 1.75,
  })
  const allergyText = parseLeadingSymbolLabel(dinh_danh.di_ung_text ?? '').text.trim() || MISSING
  const allergyVariant = dinh_danh.di_ung_ma === 'khong_di_ung_da_hoi' ? 'outline' : 'soft'

  const sortedDiagnoses = sortDiagnosesPrimaryFirst(tom_tat.chan_doan)
  const hasMoreDiagnoses = sortedDiagnoses.length > MAX_VISIBLE_DIAGNOSES
  const visibleDiagnoses =
    hasMoreDiagnoses && !diagnosesExpanded
      ? sortedDiagnoses.slice(0, MAX_VISIBLE_DIAGNOSES)
      : sortedDiagnoses

  const metricByFormula = new Map<string, ChiSo>(chi_so.map((m) => [m.cong_thuc, m]))
  const orderedMetrics = METRIC_ORDER.map((spec) => ({
    ...spec,
    metric: metricByFormula.get(spec.key) ?? null,
  }))

  return (
    <div className="flex flex-col gap-2.5 rounded-md border border-line bg-surface p-2.5 text-fg select-text">
      {/* 1. Họ tên in hoa + giới · tuổi */}
      <div className="flex flex-col gap-0.5 border-b border-line pb-2">
        <h2 className="text-sm font-semibold tracking-tight text-fg leading-snug break-words">
          {summary.hoTen}
        </h2>
        <p className="text-xs text-fg-muted tabular-nums">{summary.genderAgeText}</p>
      </div>

      {/* 2–3. Mã hồ sơ · Ngày sinh và Cân nặng · Chiều cao */}
      <dl className="grid grid-cols-2 gap-x-2 gap-y-2 text-xs">
        <div className="min-w-0">
          <dt className="text-fg-subtle">Mã hồ sơ</dt>
          <dd
            className={cn(
              'mt-0.5 break-all tabular-nums',
              summary.maHoSo !== MISSING
                ? 'font-mono font-medium text-fg'
                : 'text-fg-muted',
            )}
          >
            {summary.maHoSo}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-fg-subtle">Ngày sinh</dt>
          <dd
            className={cn(
              'mt-0.5 tabular-nums',
              summary.ngaySinh !== MISSING
                ? 'font-mono font-medium text-fg'
                : 'text-fg-muted',
            )}
          >
            {summary.ngaySinh}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-fg-subtle">Cân nặng</dt>
          <dd
            className={cn(
              'mt-0.5 tabular-nums',
              summary.canNang !== MISSING
                ? 'font-mono font-medium text-fg'
                : 'text-fg-muted',
            )}
          >
            {summary.canNang}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-fg-subtle">Chiều cao</dt>
          <dd
            className={cn(
              'mt-0.5 tabular-nums',
              summary.chieuCao !== MISSING
                ? 'font-mono font-medium text-fg'
                : 'text-fg-muted',
            )}
          >
            {summary.chieuCao}
          </dd>
        </div>
      </dl>

      {/* 4. BHYT */}
      <div className="flex flex-col gap-0.5 border-t border-line pt-2 text-xs">
        <span className="text-fg-subtle">BHYT</span>
        {summary.soTheBhyt || summary.hanBhyt !== MISSING ? (
          <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 leading-snug">
            <span
              className={
                summary.soTheBhyt
                  ? 'font-mono font-medium text-fg break-all'
                  : 'text-fg-muted'
              }
            >
              {summary.soTheBhyt ?? MISSING}
            </span>
            <span className="text-fg-subtle">
              hạn{' '}
              <span
                className={
                  summary.hanBhyt !== MISSING
                    ? 'font-mono font-medium text-fg tabular-nums'
                    : 'text-fg-muted'
                }
              >
                {summary.hanBhyt}
              </span>
            </span>
          </div>
        ) : (
          <span className="text-fg-muted">{MISSING}</span>
        )}
      </div>

      {/* 5. Dị ứng */}
      <div className="flex flex-col gap-1 border-t border-line pt-2 text-xs">
        <span className="text-fg-subtle">Dị ứng</span>
        <div>
          <Badge
            tone={allergyTone}
            variant={allergyVariant}
            icon={allergyIconEl}
            className={cn(
              'max-w-full whitespace-normal text-left leading-snug',
              dinh_danh.di_ung_ma === 'co_di_ung' && 'font-semibold',
              dinh_danh.di_ung_ma === 'chua_co_thong_tin' && 'border-dashed font-semibold',
            )}
          >
            {allergyText}
          </Badge>
        </div>
      </div>

      {/* 6. Chẩn đoán */}
      <div className="flex flex-col gap-1 border-t border-line pt-2 text-xs">
        <span className="text-fg-subtle">Chẩn đoán</span>
        {sortedDiagnoses.length === 0 ? (
          <span className="text-fg-muted">{MISSING}</span>
        ) : (
          <>
            <ul id={diagnosisListId} className="flex flex-col gap-1">
              {visibleDiagnoses.map((cd, idx) => {
                const primary = isPrimaryDiagnosis(cd)
                return (
                  <li
                    key={`${cd.loai_nhan}-${cd.ma_icd10 ?? ''}-${cd.noi_dung}-${idx}`}
                    className="leading-snug text-fg break-words"
                  >
                    <span className={primary ? 'font-medium text-fg' : 'text-fg-muted'}>
                      {cd.noi_dung?.trim() || MISSING}
                    </span>
                    {cd.ma_icd10 ? (
                      <span className="ml-1 font-mono text-2xs text-fg-subtle">
                        ({cd.ma_icd10})
                      </span>
                    ) : null}
                  </li>
                )
              })}
            </ul>
            {hasMoreDiagnoses ? (
              <button
                type="button"
                aria-expanded={diagnosesExpanded}
                aria-controls={diagnosisListId}
                onClick={() => setDiagnosesExpanded((prev) => !prev)}
                className="mt-0.5 inline-flex min-h-7 self-start cursor-pointer items-center rounded-sm px-1.5 text-xs font-medium text-primary transition-colors duration-120 hover:bg-primary-soft hover:text-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                {diagnosesExpanded ? 'Thu gọn' : 'Xem thêm'}
              </button>
            ) : null}
          </>
        )}
      </div>

      {/* 7. Chỉ số: lưới 2 cột (BMI, BSA, CrCl, eGFR) */}
      <div className="flex flex-col gap-1.5 border-t border-line pt-2 text-xs">
        <span className="text-fg-subtle">Chỉ số</span>
        <div aria-label="Bốn chỉ số lâm sàng" className="grid grid-cols-2 gap-1.5">
          {orderedMetrics.map(({ key, label, metric }) => {
            if (!metric) {
              return (
                <div
                  key={key}
                  className="flex min-w-0 flex-col justify-between rounded-sm border border-line bg-surface-muted/60 px-2 py-1.5 font-mono text-xs tabular-nums"
                >
                  <span className="font-sans text-2xs font-medium text-fg-subtle">{label}</span>
                  <span className="mt-0.5 font-semibold text-fg-muted">—</span>
                </div>
              )
            }

            const rawValue = metric.gia_tri_text?.trim() || '—'
            const isMissing = metric.thieu.length > 0 || rawValue === '—'
            const isCrclAbnormal =
              metric.cong_thuc === 'cockcroft_gault' &&
              dinh_danh.crcl_bat_thuong &&
              rawValue !== '—'
            const parsedVal = parseTrendValue(rawValue)
            const valueText = formatClinicalText(parsedVal.text)
            const unitText =
              metric.don_vi && rawValue !== '—' ? formatClinicalText(metric.don_vi) : ''

            const tileClass = cn(
              'flex min-w-0 flex-col justify-between rounded-sm border px-2 py-1.5 text-left transition-colors duration-120',
              onOpenEvidence &&
                'cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
              isCrclAbnormal
                ? cn(
                    'border-danger-line bg-danger-bg/80 text-danger-fg',
                    onOpenEvidence && 'hover:bg-danger-bg',
                  )
                : isMissing
                  ? cn(
                      'border-missing-line bg-missing-bg/70 text-missing-fg',
                      onOpenEvidence && 'hover:bg-missing-bg',
                    )
                  : cn(
                      'border-line bg-surface-muted/40 text-fg',
                      onOpenEvidence && 'hover:border-line-strong hover:bg-surface-hover',
                    ),
            )

            const tileContent = (
              <>
                <span className="flex items-center justify-between gap-1 text-2xs font-medium text-fg-subtle">
                  <span>{label}</span>
                  {isCrclAbnormal ? (
                    <ArrowDown
                      className="size-3 shrink-0 text-danger-fg"
                      strokeWidth={2}
                      aria-hidden="true"
                    />
                  ) : isMissing ? (
                    <CircleHelp
                      className="size-3 shrink-0 text-missing-fg"
                      strokeWidth={1.75}
                      aria-hidden="true"
                    />
                  ) : null}
                </span>
                <span className="mt-0.5 flex flex-wrap items-baseline gap-x-1 gap-y-0 font-mono text-xs leading-tight tabular-nums">
                  <span className="font-semibold">{valueText}</span>
                  {unitText ? (
                    <span className="break-words text-2xs text-fg-subtle">{unitText}</span>
                  ) : null}
                </span>
              </>
            )

            if (!onOpenEvidence) {
              return (
                <div
                  key={key}
                  title={
                    isMissing && metric.thieu.length > 0
                      ? `Thiếu: ${metric.thieu.join(', ')}`
                      : undefined
                  }
                  className={tileClass}
                >
                  {tileContent}
                </div>
              )
            }

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
                className={tileClass}
              >
                {tileContent}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
