import { ArrowDown, CircleHelp } from 'lucide-react'
import { createElement } from 'react'
import type { ChiSo, DinhDanhCa, TomTat } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { RecordId } from '@/components/ui/record-id'
import { cn } from '@/lib/cn'
import { parseLeadingSymbolLabel, parseTrendValue } from '@/lib/displayFormat'
import { iconOfAllergy, toneOfAllergy } from '@/lib/severity'
import type { EvidenceTarget } from '@/lib/uiTypes'

export interface OrderHeaderStripProps {
  dinhDanh: DinhDanhCa
  tomTat: TomTat
  chiSo: readonly ChiSo[]
  onOpenEvidence: (target: EvidenceTarget, trigger: HTMLButtonElement) => void
}

const METRIC_SHORT_LABELS: Record<string, string> = {
  cockcroft_gault: 'CrCl',
  egfr_ckd_epi_2021: 'eGFR',
  bmi: 'BMI',
  bsa_mosteller: 'BSA',
}

/** Dải tóm tắt người bệnh đặt dưới thanh thẻ: hành chính, dị ứng, chẩn đoán chính và 4 chỉ số. */
export function OrderHeaderStrip({
  dinhDanh,
  tomTat,
  chiSo,
  onOpenEvidence,
}: OrderHeaderStripProps) {
  const allergyTone = toneOfAllergy(dinhDanh.di_ung_ma)
  const allergyIconEl = createElement(iconOfAllergy(dinhDanh.di_ung_ma), {
    className: 'size-3.5',
    strokeWidth: 1.75,
  })
  const allergyText = parseLeadingSymbolLabel(dinhDanh.di_ung_text).text
  const allergyVariant = dinhDanh.di_ung_ma === 'khong_di_ung_da_hoi' ? 'outline' : 'soft'

  const primaryDiagnosis = tomTat.chan_doan[0] ?? null

  return (
    <section
      aria-label="Thông tin người bệnh và chỉ số lâm sàng"
      className="order-header mx-auto w-full max-w-[960px] px-5 pt-3.5 pb-3 border-b border-line flex flex-col gap-2"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-fg-muted">
          <span className="font-medium text-fg">{dinhDanh.gioi_tuoi}</span>
          <span className="text-fg-disabled" aria-hidden="true">
            ·
          </span>
          <span className="font-mono tabular-nums">{dinhDanh.can_nang}</span>
          <span className="text-fg-disabled" aria-hidden="true">
            ·
          </span>
          <span>{dinhDanh.khoa_loai}</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-muted min-w-0">
          <Badge
            tone={allergyTone}
            variant={allergyVariant}
            icon={allergyIconEl}
            className={cn(
              'whitespace-normal text-left',
              dinhDanh.di_ung_ma === 'co_di_ung' && 'font-semibold',
              dinhDanh.di_ung_ma === 'chua_co_thong_tin' && 'border-dashed font-semibold',
            )}
          >
            {allergyText}
          </Badge>
          {primaryDiagnosis ? (
            <span className="inline-flex flex-wrap items-center gap-1.5">
              <span className="text-fg-subtle">{primaryDiagnosis.loai_nhan}:</span>
              <span className="font-medium text-fg">{primaryDiagnosis.noi_dung}</span>
              {primaryDiagnosis.ma_icd10 ? <RecordId id={primaryDiagnosis.ma_icd10} /> : null}
            </span>
          ) : (
            <span className="text-fg-subtle">Chưa ghi nhận chẩn đoán chính</span>
          )}
          {tomTat.co_dia.length > 0 ? (
            <span className="text-fg-subtle">· Cơ địa: {tomTat.co_dia.join(', ')}</span>
          ) : null}
        </div>
      </div>

      <div
        className="flex flex-wrap items-center gap-1.5 font-mono text-xs tabular-nums"
        aria-label="Bốn chỉ số lâm sàng"
      >
        {chiSo.map((metric) => {
          const shortName = METRIC_SHORT_LABELS[metric.cong_thuc] ?? metric.nhan
          const isCrclAbnormal =
            metric.cong_thuc === 'cockcroft_gault' &&
            dinhDanh.crcl_bat_thuong &&
            metric.gia_tri_text !== '—'
          const isMissing = metric.thieu.length > 0 || metric.gia_tri_text === '—'
          const parsedVal = parseTrendValue(metric.gia_tri_text)

          return (
            <button
              key={metric.cong_thuc}
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
                  : `Bấm để xem phép tính ${metric.nhan}`
              }
              className={cn(
                'inline-flex cursor-pointer items-center gap-1.5 rounded-sm border px-2 py-0.5 transition-colors duration-120',
                isCrclAbnormal
                  ? 'border-danger-line bg-danger-bg/80 text-danger-fg hover:bg-danger-bg'
                  : isMissing
                    ? 'border-missing-line bg-missing-bg/80 text-missing-fg hover:bg-missing-bg'
                    : 'border-line bg-surface text-fg hover:border-line-strong hover:bg-surface-hover',
              )}
            >
              <span className="text-fg-subtle">{shortName}</span>
              <span className="font-semibold">{parsedVal.text}</span>
              {metric.don_vi && metric.gia_tri_text !== '—' ? (
                <span className="text-2xs text-fg-subtle">{metric.don_vi}</span>
              ) : null}
              {isCrclAbnormal ? (
                <ArrowDown className="size-3 shrink-0" strokeWidth={1.75} aria-hidden="true" />
              ) : null}
              {isMissing ? (
                <CircleHelp className="size-3 shrink-0" strokeWidth={1.75} aria-hidden="true" />
              ) : null}
            </button>
          )
        })}
      </div>
    </section>
  )
}
